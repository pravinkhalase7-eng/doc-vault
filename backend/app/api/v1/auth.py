from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.google import (
    decode_oauth_state,
    exchange_google_code,
    google_authorize_url,
    google_enabled,
    google_redirect_enabled,
    issue_login_ticket,
    redeem_login_ticket,
    upsert_google_user,
    verify_google_id_token,
)
from app.auth.security import totp_secret, totp_uri, verify_totp
from app.auth.service import (
    authenticate,
    client_ip,
    get_current_user,
    issue_session,
    log_security_event,
    register_user,
    request_password_reset,
    reset_password,
    revoke_refresh,
    rotate_refresh,
    seed_guest_user,
    verify_email,
)
from app.config import get_settings
from app.database import get_db
from app.email.template_service import send_templated
from app.exceptions import AppError, UnauthorizedError
from app.logging import get_logger
from app.models.user import User
from app.schemas.common import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
    UserOut,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
log = get_logger("auth")


def ok(data):
    return {"success": True, "data": data}


@router.post("/register")
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user, token = await register_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        ip=client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    await send_templated(
        user.email,
        "verify_email",
        "Verify your DocVault email",
        link=f"{settings.app_url}/verify?token={token}",
    )
    await send_templated(user.email, "welcome", "Welcome to DocVault", link=settings.app_url)
    return ok({"user": UserOut.model_validate(user).model_dump(), "verification_required": True})


@router.post("/login")
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user, access, refresh = await authenticate(
        db,
        email=payload.email,
        password=payload.password,
        totp_code=payload.totp_code,
        ip=client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    return ok(
        {
            **TokenPair(access_token=access, refresh_token=refresh).model_dump(),
            "user": UserOut.model_validate(user).model_dump(),
        }
    )


@router.post("/guest")
async def guest_login(request: Request, db: AsyncSession = Depends(get_db)):
    await seed_guest_user(db)
    user, access, refresh = await authenticate(
        db,
        email=settings.guest_email,
        password=settings.guest_password,
        totp_code=None,
        ip=client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    return ok(
        {
            **TokenPair(access_token=access, refresh_token=refresh).model_dump(),
            "user": UserOut.model_validate(user).model_dump(),
        }
    )


@router.get("/google/config")
async def google_config():
    return ok(
        {
            "enabled": google_enabled(),
            "redirect": google_redirect_enabled(),
            "client_id": settings.google_client_id or None,
        }
    )


@router.get("/google")
async def google_start(request: Request):
    next_path = request.query_params.get("next")
    try:
        return RedirectResponse(google_authorize_url(next_path), status_code=302)
    except AppError:
        return RedirectResponse(f"{settings.app_url.rstrip('/')}/login?error=google_not_configured", status_code=302)


@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    app = settings.app_url.rstrip("/")
    if request.query_params.get("error"):
        return RedirectResponse(f"{app}/login?error=google_denied", status_code=302)
    code = (request.query_params.get("code") or "").strip()
    state = (request.query_params.get("state") or "").strip()
    if not code or not state:
        return RedirectResponse(f"{app}/login?error=google", status_code=302)
    try:
        next_path = decode_oauth_state(state)
        profile = await exchange_google_code(code)
        user = await upsert_google_user(db, profile)
        ticket = await issue_login_ticket(db, user)
        await log_security_event(
            db,
            "google_login",
            user_id=user.id,
            ip=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
        await db.commit()
    except AppError as exc:
        await db.rollback()
        err = "google_guest" if exc.code == "GOOGLE_GUEST" else "google"
        return RedirectResponse(f"{app}/login?error={err}", status_code=302)
    except Exception:
        log.exception("Google OAuth callback failed")
        await db.rollback()
        return RedirectResponse(f"{app}/login?error=google", status_code=302)
    from urllib.parse import urlencode

    return RedirectResponse(f"{app}/auth/google?{urlencode({'ticket': ticket, 'next': next_path})}", status_code=302)


@router.post("/google")
async def google_finish(payload: GoogleAuthRequest, request: Request, db: AsyncSession = Depends(get_db)):
    from datetime import UTC, datetime

    ticket = (payload.ticket or "").strip()
    id_tok = (payload.id_token or "").strip()
    if ticket:
        user = await redeem_login_ticket(db, ticket)
    elif id_tok:
        profile = verify_google_id_token(id_tok)
        user = await upsert_google_user(db, profile)
        await log_security_event(
            db,
            "google_login",
            user_id=user.id,
            ip=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
    else:
        raise UnauthorizedError("INVALID_GOOGLE", "Google sign-in did not complete. Try again.")
    access, refresh = await issue_session(
        db, user, ip=client_ip(request), user_agent=request.headers.get("User-Agent")
    )
    user.last_login_at = datetime.now(UTC)
    user.last_login_ip = client_ip(request)
    await db.commit()
    return ok(
        {
            **TokenPair(access_token=access, refresh_token=refresh).model_dump(),
            "user": UserOut.model_validate(user).model_dump(),
        }
    )


@router.post("/refresh")
async def refresh(payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    access, refresh_token = await rotate_refresh(db, payload.refresh_token, client_ip(request), request.headers.get("User-Agent"))
    return ok(TokenPair(access_token=access, refresh_token=refresh_token).model_dump())


@router.post("/logout")
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await revoke_refresh(db, payload.refresh_token)
    return ok({"logged_out": True})


@router.post("/verify-email")
async def verify(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    user = await verify_email(db, payload.token)
    return ok({"verified": True, "user_id": user.id})


@router.post("/forgot-password")
async def forgot(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    token = await request_password_reset(db, payload.email)
    if token:
        from sqlalchemy import select
        from app.models.user import User as UserModel

        user = await db.scalar(select(UserModel).where(UserModel.email == payload.email.lower()))
        if user:
            await send_templated(
                user.email,
                "password_reset",
                "Reset your DocVault password",
                link=f"{settings.app_url}/reset-password?token={token}",
            )
    return ok({"sent": True})


@router.post("/reset-password")
async def reset(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await reset_password(db, payload.token, payload.password)
    return ok({"reset": True})


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return ok(UserOut.model_validate(user).model_dump())


@router.post("/2fa/setup")
async def setup_2fa(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    secret = totp_secret()
    user.totp_secret = secret
    await db.commit()
    return ok({"secret": secret, "otpauth_url": totp_uri(user.email, secret)})


@router.post("/2fa/enable")
async def enable_2fa(payload: dict, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    code = str(payload.get("code") or "")
    if not user.totp_secret or not verify_totp(user.totp_secret, code):
        raise UnauthorizedError("INVALID_2FA", "Invalid authenticator code")
    user.totp_enabled = True
    await db.commit()
    return ok({"totp_enabled": True})
