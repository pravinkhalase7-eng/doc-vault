from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import get_current_admin
from app.config import get_settings
from app.database import get_db, engine
from app.models.ai import AIAuditLog
from app.models.document import Document
from app.models.notification import EmailLog
from app.models.system import BackupRecord, StorageUsage
from app.models.user import User
from app.storage.local import storage_root

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


def ok(data):
    return {"success": True, "data": data}


@router.get("/overview")
async def overview(_admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    users = await db.scalar(select(func.count()).select_from(User).where(User.deleted_at.is_(None)))
    docs = await db.scalar(select(func.count()).select_from(Document).where(Document.deleted_at.is_(None)))
    ai = await db.scalar(select(func.count()).select_from(AIAuditLog))
    emails = await db.scalar(select(func.count()).select_from(EmailLog))
    failed = await db.scalar(
        select(func.count()).select_from(Document).where(Document.status == "FAILED")
    )
    storage = await db.scalar(select(func.coalesce(func.sum(StorageUsage.used_bytes), 0)))
    last_backup = await db.scalar(select(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(1))
    disk = storage_root()
    usage = disk.stat().st_size if disk.exists() else 0
    return ok(
        {
            "users": int(users or 0),
            "documents": int(docs or 0),
            "ai_requests": int(ai or 0),
            "email_logs": int(emails or 0),
            "failed_jobs": int(failed or 0),
            "storage_used_bytes": int(storage or 0),
            "disk_path_exists": disk.exists(),
            "last_backup": {
                "status": last_backup.status if last_backup else None,
                "finished_at": last_backup.finished_at if last_backup else None,
                "size_bytes": last_backup.size_bytes if last_backup else None,
            },
        }
    )


@router.get("/users")
async def users(_admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(User).where(User.deleted_at.is_(None)).limit(200))).all()
    return ok(
        [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role.value,
                "is_active": u.is_active,
                "created_at": u.created_at,
            }
            for u in rows
        ]
    )
