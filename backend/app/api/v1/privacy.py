from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import get_current_user
from app.database import get_db
from app.models.ai import AIAuditLog, AIConversation, AIEvidence, AIFeedback, AIMessage
from app.models.document import Document, DocumentChunk, DocumentMetadata
from app.models.notification import Notification
from app.models.system import StorageUsage
from app.models.user import User

router = APIRouter(tags=["privacy"])


def ok(data):
    return {"success": True, "data": data}


@router.get("/privacy/center")
async def privacy_center(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    prefs = user.preferences
    docs = await db.scalar(
        select(func.count()).select_from(Document).where(Document.user_id == user.id, Document.deleted_at.is_(None))
    )
    external = await db.scalar(
        select(func.count()).select_from(AIAuditLog).where(AIAuditLog.user_id == user.id, AIAuditLog.external_ai.is_(True))
    )
    today = datetime.now(UTC).date()
    today_count = await db.scalar(
        select(func.count()).select_from(AIAuditLog).where(
            AIAuditLog.user_id == user.id, func.date(AIAuditLog.created_at) == today
        )
    )
    highly = await db.scalar(
        select(func.count()).select_from(AIAuditLog).where(
            AIAuditLog.user_id == user.id, AIAuditLog.external_ai.is_(True), AIAuditLog.privacy_decision == "highly"
        )
    )
    return ok(
        {
            "private_ai": True,
            "cloud_ai": bool(prefs and prefs.external_ai_enabled),
            "privacy_mode": prefs.ai_privacy_mode.value if prefs else "PRIVATE",
            "documents_processed": int(docs or 0),
            "external_ai_requests": int(external or 0),
            "highly_sensitive_external": int(highly or 0),
            "ai_access_today": int(today_count or 0),
        }
    )


@router.get("/privacy/activity")
async def privacy_activity(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(AIAuditLog).where(AIAuditLog.user_id == user.id).order_by(AIAuditLog.created_at.desc()).limit(50)
        )
    ).all()
    return ok(
        [
            {
                "id": r.id,
                "timestamp": r.created_at,
                "operation": r.operation.value,
                "documents_accessed": len(r.documents_accessed or []),
                "tool_called": r.tool_called,
                "model": r.model,
                "external_ai": r.external_ai,
                "success": r.success,
                "fields_used": r.fields_used,
                "raw_document_sent": r.raw_document_sent,
            }
            for r in rows
        ]
    )


@router.delete("/privacy/ai-data")
async def delete_ai_data(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    for model in (AIEvidence, AIFeedback, AIMessage, AIConversation, AIAuditLog, DocumentChunk):
        rows = (await db.scalars(select(model).where(model.user_id == user.id))).all() if hasattr(model, "user_id") else []
        if model is AIMessage:
            convos = (await db.scalars(select(AIConversation).where(AIConversation.user_id == user.id))).all()
            for conv in convos:
                await db.delete(conv)
        elif model is AIConversation:
            continue
        else:
            for row in rows:
                await db.delete(row)
    metas = (await db.scalars(select(DocumentMetadata).where(DocumentMetadata.user_id == user.id))).all()
    for meta in metas:
        if meta.source == "ai":
            await db.delete(meta)
    await db.commit()
    return ok({"deleted": True})


@router.get("/notifications")
async def notifications(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50)
        )
    ).all()
    return ok(
        [
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "kind": n.kind,
                "read_at": n.read_at,
                "link": n.link,
                "created_at": n.created_at,
            }
            for n in rows
        ]
    )


@router.post("/notifications/{notification_id}/read")
async def read_notification(
    notification_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rec = await db.get(Notification, notification_id)
    if rec and rec.user_id == user.id:
        rec.read_at = datetime.now(UTC)
        await db.commit()
    return ok({"read": True})


@router.get("/audit")
async def audit(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models.system import SecurityEvent

    rows = (
        await db.scalars(
            select(SecurityEvent)
            .where(SecurityEvent.user_id == user.id)
            .order_by(SecurityEvent.created_at.desc())
            .limit(50)
        )
    ).all()
    return ok(
        [
            {
                "id": e.id,
                "event_type": e.event_type,
                "success": e.success,
                "ip_address": e.ip_address,
                "created_at": e.created_at,
            }
            for e in rows
        ]
    )


@router.get("/storage")
async def storage(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    usage = await db.scalar(select(StorageUsage).where(StorageUsage.user_id == user.id))
    if not usage:
        return ok({"used_bytes": 0, "quota_bytes": 0, "remaining_bytes": 0, "file_count": 0})
    return ok(
        {
            "used_bytes": usage.used_bytes,
            "quota_bytes": usage.quota_bytes,
            "remaining_bytes": max(0, usage.quota_bytes - usage.used_bytes),
            "file_count": usage.file_count,
            "percent": int(usage.used_bytes * 100 / usage.quota_bytes) if usage.quota_bytes else 0,
        }
    )
