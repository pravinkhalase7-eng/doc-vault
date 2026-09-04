"""Google sign-in: verify ID tokens, OAuth code exchange, and one-time login tickets."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import generate_token, hash_token
from app.config import get_settings
from app.exceptions import AppError, UnauthorizedError
from app.models.enums import AIPrivacyMode, LanguageCode, ThemePreference, UserRole
from app.models.system import StorageUsage
from app.models.user import LoginTicket, User, UserPreference

settings = get_settings()

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"


def google_enabled() -> bool:
    return bool(settings.google_client_id)


def google_redirect_enabled() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def google_redirect_uri() -> str:
    return f"{settings.app_url.rstrip('/')}/api/v1/auth/google/callback"


def safe_next(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//") or "://" in value or "\\" in value:
        return "/home"
    return value


def encode_oauth_state(next_path: str | None) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "type": "google_oauth",
            "next": safe_next(next_path),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_oauth_state(state: str) -> str:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("INVALID_GOOGLE", "Google sign-in expired. Try again.") from exc
    if payload.get("type") != "google_oauth":
        raise UnauthorizedError("INVALID_GOOGLE", "Google sign-in expired. Try again.")
    return safe_next(payload.get("next"))


def google_authorize_url(next_path: str | None) -> str:
    if not google_redirect_enabled():
        raise AppError("GOOGLE_NOT_CONFIGURED", "Google sign-in is not set up on this server.", 503)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": encode_oauth_state(next_path),
    }
    return f"{GOOGLE_AUTH}?{urlencode(params)}"


def _google_profile_from_idinfo(info: dict) -> dict:
    sub = str(info.get("sub") or "").strip()
    email = str(info.get("email") or "").strip().lower()
    if not sub or not email:
        raise UnauthorizedError("INVALID_GOOGLE", "Google did not return an email for this account.")
    if not info.get("email_verified", False):
        raise UnauthorizedError("INVALID_GOOGLE", "Verify your Google email, then try again.")
    name = str(info.get("name") or email.split("@")[0]).strip() or "Vault user"
    return {"sub": sub, "email": email, "full_name": name[:200]}


def verify_google_id_token(token: str) -> dict:
    if not google_enabled():
        raise AppError("GOOGLE_NOT_CONFIGURED", "Google sign-in is not set up on this server.", 503)
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError as exc:
        raise AppError("GOOGLE_NOT_CONFIGURED", "Google sign-in is not available.", 503) from exc
    try:
        info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.google_client_id,
            clock_skew_in_seconds=10,
        )
    except Exception as exc:
        raise UnauthorizedError("INVALID_GOOGLE", "Google could not verify that sign-in.") from exc
    iss = str(info.get("iss") or "")
    if iss not in {"accounts.google.com", "https://accounts.google.com"}:
        raise UnauthorizedError("INVALID_GOOGLE", "Google could not verify that sign-in.")
    return _google_profile_from_idinfo(info)


async def exchange_google_code(code: str) -> dict:
    if not google_redirect_enabled():
        raise AppError("GOOGLE_NOT_CONFIGURED", "Google sign-in is not set up on this server.", 503)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": google_redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
    if response.status_code >= 400:
        raise UnauthorizedError("INVALID_GOOGLE", "Google sign-in did not complete. Try again.")
    payload = response.json()
    id_tok = str(payload.get("id_token") or "")
    if not id_tok:
        raise UnauthorizedError("INVALID_GOOGLE", "Google sign-in did not complete. Try again.")
    return verify_google_id_token(id_tok)


async def upsert_google_user(db: AsyncSession, profile: dict) -> User:
    email = profile["email"]
    sub = profile["sub"]
    if email == settings.guest_email.lower():
        raise AppError("GOOGLE_GUEST", "The guest vault cannot be linked to Google. Create your own vault.", 400)

    user = await db.scalar(
        select(User)
        .options(selectinload(User.preferences))
        .where(User.google_sub == sub, User.deleted_at.is_(None))
    )
    if user:
        if user.email != email:
            taken = await db.scalar(select(User.id).where(User.email == email, User.deleted_at.is_(None), User.id != user.id))
            if not taken:
                user.email = email
        if not user.email_verified_at:
            user.email_verified_at = datetime.now(UTC)
        return user

    user = await db.scalar(
        select(User)
        .options(selectinload(User.preferences))
        .where(User.email == email, User.deleted_at.is_(None))
    )
    if user:
        if user.google_sub and user.google_sub != sub:
            raise AppError("EMAIL_EXISTS", "An account with this email already exists", 409)
        user.google_sub = sub
        if not user.email_verified_at:
            user.email_verified_at = datetime.now(UTC)
        return user

    user = User(
        email=email,
        password_hash=None,
        google_sub=sub,
        full_name=profile["full_name"],
        role=UserRole.USER,
        email_verified_at=datetime.now(UTC),
        onboarding_completed=False,
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
    from app.family.service import claim_family_invites

    await claim_family_invites(db, user)
    return user


async def issue_login_ticket(db: AsyncSession, user: User) -> str:
    raw = generate_token()
    db.add(
        LoginTicket(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(minutes=2),
        )
    )
    return raw


async def redeem_login_ticket(db: AsyncSession, ticket: str) -> User:
    rec = await db.scalar(
        select(LoginTicket).where(LoginTicket.token_hash == hash_token(ticket), LoginTicket.used_at.is_(None))
    )
    if not rec or rec.expires_at < datetime.now(UTC):
        raise UnauthorizedError("INVALID_GOOGLE", "Google sign-in expired. Try again.")
    user = await db.scalar(
        select(User).options(selectinload(User.preferences)).where(User.id == rec.user_id, User.deleted_at.is_(None))
    )
    if not user or not user.is_active:
        raise UnauthorizedError("INVALID_GOOGLE", "Google sign-in expired. Try again.")
    rec.used_at = datetime.now(UTC)
    return user
