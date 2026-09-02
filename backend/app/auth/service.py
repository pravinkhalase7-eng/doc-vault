from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
    verify_totp,
)
from app.config import get_settings
from app.database import get_db
from app.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.models.enums import AIPrivacyMode, LanguageCode, ThemePreference, UserRole
from app.models.system import SecurityEvent, StorageUsage
from app.models.user import (
    EmailVerificationToken,
    PasswordResetToken,
    User,
    UserPreference,
    UserSession,
)

settings = get_settings()


async def log_security_event(
    db: AsyncSession,
    event_type: str,
    *,
    user_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    success: bool = True,
    detail: str | None = None,
) -> None:
    db.add(
        SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip,
            user_agent=user_agent,
            success=success,
            detail=detail,
        )
    )


async def register_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str]:
    existing = await db.scalar(select(User).where(User.email == email.lower(), User.deleted_at.is_(None)))
    if existing:
        raise ConflictError("EMAIL_EXISTS", "An account with this email already exists")

    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        full_name=full_name,
        role=UserRole.USER,
    )
    db.add(user)
    await db.flush()
    db.add(
        UserPreference(
            user_id=user.id,
            language=LanguageCode.EN,
            theme=ThemePreference.SYSTEM,
            ai_privacy_mode=AIPrivacyMode.PRIVATE,
            external_ai_enabled=False,
        )
    )
    db.add(
        StorageUsage(
            user_id=user.id,
            used_bytes=0,
            quota_bytes=settings.default_storage_quota_bytes,
            file_count=0,
        )
    )
    raw = generate_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )
    await log_security_event(db, "register", user_id=user.id, ip=ip, user_agent=user_agent)
    from app.family.service import claim_family_invites

    await claim_family_invites(db, user)
    await db.commit()
    await db.refresh(user)
    return user, raw


async def seed_guest_user(db: AsyncSession) -> None:
    email = settings.guest_email.lower()
    existing = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if not existing:
        existing = await db.scalar(
            select(User).where(User.email == "guest@docvault.local", User.deleted_at.is_(None))
        )
        if existing:
            existing.email = email
    if existing:
        existing.password_hash = hash_password(settings.guest_password)
        existing.full_name = existing.full_name or "Guest"
        existing.is_active = True
        existing.onboarding_completed = True
        if not existing.email_verified_at:
            existing.email_verified_at = datetime.now(UTC)
        await db.commit()
        return

    user = User(
        email=email,
        password_hash=hash_password(settings.guest_password),
        full_name="Guest",
        role=UserRole.USER,
        email_verified_at=datetime.now(UTC),
        onboarding_completed=True,
    )
    db.add(user)
    await db.flush()
    db.add(
        UserPreference(
            user_id=user.id,
            language=LanguageCode.EN,
            theme=ThemePreference.DARK,
            ai_privacy_mode=AIPrivacyMode.PRIVATE,
            external_ai_enabled=False,
        )
    )
    db.add(
        StorageUsage(
            user_id=user.id,
            used_bytes=0,
            quota_bytes=settings.default_storage_quota_bytes,
            file_count=0,
        )
    )
    await db.commit()


async def authenticate(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    totp_code: str | None,
    ip: str | None,
    user_agent: str | None,
) -> tuple[User, str, str]:
    user = await db.scalar(
        select(User)
        .options(selectinload(User.preferences))
        .where(User.email == email.lower(), User.deleted_at.is_(None))
    )
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        await log_security_event(db, "login_failed", ip=ip, user_agent=user_agent, success=False, detail=email.lower())
        await db.commit()
        raise UnauthorizedError("INVALID_CREDENTIALS", "Invalid email or password")

    if user.totp_enabled:
        if not totp_code or not user.totp_secret or not verify_totp(user.totp_secret, totp_code):
            await log_security_event(db, "2fa_failed", user_id=user.id, ip=ip, success=False)
            await db.commit()
            raise UnauthorizedError("INVALID_2FA", "A valid authenticator code is required")

    access, refresh = await issue_session(db, user, ip=ip, user_agent=user_agent)
    user.last_login_at = datetime.now(UTC)
    user.last_login_ip = ip
    await log_security_event(db, "login", user_id=user.id, ip=ip, user_agent=user_agent)
    await db.commit()
    return user, access, refresh


async def issue_session(
    db: AsyncSession, user: User, *, ip: str | None, user_agent: str | None, rotated_from_id: str | None = None
) -> tuple[str, str]:
    raw_refresh = generate_token()
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_token(raw_refresh),
        user_agent=user_agent,
        ip_address=ip,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        rotated_from_id=rotated_from_id,
    )
    db.add(session)
    await db.flush()
    access = create_access_token(user.id, user.role.value)
    return access, raw_refresh


async def rotate_refresh(db: AsyncSession, refresh_token: str, ip: str | None, user_agent: str | None) -> tuple[str, str]:
    token_h = hash_token(refresh_token)
    session = await db.scalar(select(UserSession).where(UserSession.refresh_token_hash == token_h))
    if not session or session.revoked_at or session.expires_at < datetime.now(UTC):
        raise UnauthorizedError("INVALID_REFRESH", "Session expired. Please sign in again.")

    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("INVALID_REFRESH", "Session expired. Please sign in again.")

    session.revoked_at = datetime.now(UTC)
    access, refresh = await issue_session(db, user, ip=ip, user_agent=user_agent, rotated_from_id=session.id)
    await db.commit()
    return access, refresh


async def revoke_refresh(db: AsyncSession, refresh_token: str) -> None:
    session = await db.scalar(select(UserSession).where(UserSession.refresh_token_hash == hash_token(refresh_token)))
    if session and not session.revoked_at:
        session.revoked_at = datetime.now(UTC)
        await db.commit()


async def verify_email(db: AsyncSession, token: str) -> User:
    rec = await db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(token),
            EmailVerificationToken.used_at.is_(None),
        )
    )
    if not rec or rec.expires_at < datetime.now(UTC):
        raise UnauthorizedError("INVALID_TOKEN", "Verification link is invalid or expired")
    user = await db.get(User, rec.user_id)
    if not user:
        raise UnauthorizedError("INVALID_TOKEN", "Verification link is invalid or expired")
    rec.used_at = datetime.now(UTC)
    user.email_verified_at = datetime.now(UTC)
    await db.commit()
    return user


async def request_password_reset(db: AsyncSession, email: str) -> str | None:
    user = await db.scalar(select(User).where(User.email == email.lower(), User.deleted_at.is_(None)))
    if not user:
        return None
    raw = generate_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )
    )
    await db.commit()
    return raw


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    rec = await db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(token),
            PasswordResetToken.used_at.is_(None),
        )
    )
    if not rec or rec.expires_at < datetime.now(UTC):
        raise UnauthorizedError("INVALID_TOKEN", "Reset link is invalid or expired")
    user = await db.get(User, rec.user_id)
    if not user:
        raise UnauthorizedError("INVALID_TOKEN", "Reset link is invalid or expired")
    user.password_hash = hash_password(new_password)
    rec.used_at = datetime.now(UTC)
    sessions = (await db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)))).all()
    now = datetime.now(UTC)
    for session in sessions:
        session.revoked_at = now
    await log_security_event(db, "password_reset", user_id=user.id)
    await db.commit()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _user_from_access_token(request, db, allow_query_token=False)


async def get_file_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Auth for file streams (preview/download) that browsers cannot header-auth (iframe, <a>)."""
    return await _user_from_access_token(request, db, allow_query_token=True)


def access_token_from_request(request: Request, *, allow_query_token: bool) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header.removeprefix("Bearer ").strip()
        if token:
            return token
    if allow_query_token:
        query = (request.query_params.get("token") or "").strip()
        if query:
            return query
    return None


async def _user_from_access_token(
    request: Request,
    db: AsyncSession,
    *,
    allow_query_token: bool,
) -> User:
    token = access_token_from_request(request, allow_query_token=allow_query_token)
    if not token:
        raise UnauthorizedError()
    try:
        from app.auth.security import decode_token

        payload = decode_token(token)
    except Exception as exc:
        raise UnauthorizedError() from exc
    user = await db.scalar(
        select(User)
        .options(selectinload(User.preferences))
        .where(User.id == payload["sub"], User.deleted_at.is_(None))
    )
    if not user or not user.is_active:
        raise UnauthorizedError()
    from app.logging import user_id_ctx

    user_id_ctx.set(user.id)
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("ADMIN_REQUIRED", "Administrator access required")
    return user


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
