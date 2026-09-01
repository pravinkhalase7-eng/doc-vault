from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import get_current_user
from app.database import get_db
from app.models.enums import AIPrivacyMode, LanguageCode
from app.models.user import User
from app.schemas.common import OnboardingRequest, PreferenceUpdate
from app.services.health_score import compute_health

router = APIRouter(prefix="/users", tags=["users"])


def ok(data):
    return {"success": True, "data": data}


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    prefs = user.preferences
    health = await compute_health(db, user.id)
    return ok(
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "email_verified_at": user.email_verified_at,
            "onboarding_completed": user.onboarding_completed,
            "totp_enabled": user.totp_enabled,
            "preferences": {
                "language": prefs.language.value if prefs else "en",
                "theme": prefs.theme.value if prefs else "SYSTEM",
                "ai_privacy_mode": prefs.ai_privacy_mode.value if prefs else "PRIVATE",
                "external_ai_enabled": bool(prefs and prefs.external_ai_enabled),
                "allow_highly_sensitive_external": bool(prefs and prefs.allow_highly_sensitive_external),
                "daily_briefing_enabled": bool(prefs and prefs.daily_briefing_enabled),
                "weekly_report_enabled": bool(prefs and prefs.weekly_report_enabled),
                "reminder_offsets_days": prefs.reminder_offsets_days if prefs else [30, 14, 7, 1],
                "naming_style": prefs.naming_style if prefs else "descriptive",
                "preferred_categories": prefs.preferred_categories if prefs else [],
                "notification_email": bool(prefs and prefs.notification_email),
                "notification_in_app": bool(prefs and prefs.notification_in_app),
                "timezone": prefs.timezone if prefs else "Asia/Kolkata",
            },
            "health": health,
        }
    )


@router.patch("/me/preferences")
async def update_prefs(
    payload: PreferenceUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    prefs = user.preferences
    data = payload.model_dump(exclude_none=True)
    onboarding = data.pop("onboarding_completed", None)
    for key, value in data.items():
        if hasattr(prefs, key):
            setattr(prefs, key, value)
    if onboarding is not None:
        user.onboarding_completed = onboarding
    await db.commit()
    return ok({"updated": True})


@router.post("/onboarding")
async def onboarding(
    payload: OnboardingRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    prefs = user.preferences
    prefs.ai_privacy_mode = AIPrivacyMode(payload.ai_privacy_mode)
    prefs.external_ai_enabled = payload.external_ai_enabled and payload.ai_privacy_mode != "PRIVATE"
    prefs.preferred_categories = payload.categories
    prefs.daily_briefing_enabled = payload.daily_briefing_enabled
    prefs.weekly_report_enabled = payload.weekly_report_enabled
    prefs.language = LanguageCode(payload.language)
    user.onboarding_completed = True
    await db.commit()
    return ok({"onboarding_completed": True})
