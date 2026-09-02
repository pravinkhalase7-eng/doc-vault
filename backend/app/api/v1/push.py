from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import get_current_user
from app.database import get_db
from app.exceptions import AppError
from app.models.user import User
from app.push.service import delete_subscription, push_configured, upsert_subscription, vapid_public_key
from app.schemas.common import APIModel

router = APIRouter(prefix="/push", tags=["push"])


def ok(data):
    return {"success": True, "data": data}


class PushSubscribeRequest(APIModel):
    endpoint: str = Field(min_length=8, max_length=2048)
    keys: dict[str, str]


class PushUnsubscribeRequest(APIModel):
    endpoint: str = Field(min_length=8, max_length=2048)


@router.get("/config")
async def push_config(user: User = Depends(get_current_user)):
    _ = user
    return ok({"enabled": push_configured(), "public_key": vapid_public_key()})


@router.post("/subscribe")
async def subscribe(
    payload: PushSubscribeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not push_configured():
        raise AppError("PUSH_DISABLED", "Push notifications are not configured on the server", 503)
    p256dh = (payload.keys or {}).get("p256dh") or ""
    auth = (payload.keys or {}).get("auth") or ""
    if not p256dh or not auth:
        raise AppError("INVALID_SUBSCRIPTION", "Push subscription keys are missing", 400)
    await upsert_subscription(
        db,
        user,
        endpoint=payload.endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=(request.headers.get("user-agent") or "")[:512],
    )
    if user.preferences:
        user.preferences.notification_push = True
    await db.commit()
    return ok({"subscribed": True})


@router.post("/unsubscribe")
async def unsubscribe(
    payload: PushUnsubscribeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_subscription(db, user, payload.endpoint)
    await db.commit()
    return ok({"subscribed": False})
