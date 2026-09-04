from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import get_current_user
from app.collections.service import (
    assert_valid_parent,
    assign_to_default_if_unfiled,
    delete_owned_collection,
    descendants_of,
    document_ids_for_collections,
    file_unfiled_into_default,
    find_owned_collection_by_name,
    is_default_collection,
    merge_same_name_collections,
    owned_collection,
    serialize_collection,
    serialize_tree_file,
)
from app.database import get_db
from app.documents.service import ensure_quota, get_document_for_user
from app.models.collection import Collection, CollectionDocument, Reminder, Task
from app.models.document import Document
from app.models.enums import DocumentStatus, TaskStatus
from app.models.user import User
from app.exceptions import NotFoundError
from app.reminders.service import cancel_reminder, reminder_view
from app.schemas.common import CollectionCreate, CollectionUpdate, ReminderCreate, TaskCreate
from app.services.health_score import compute_health
from datetime import UTC, date, datetime, timedelta

router = APIRouter(tags=["workspace"])


def ok(data):
    return {"success": True, "data": data}


PROCESSING_STATUSES = {
    DocumentStatus.UPLOADING,
    DocumentStatus.PROCESSING,
    DocumentStatus.OCR_PROCESSING,
    DocumentStatus.AI_PROCESSING,
}
READY_STATUSES = {
    DocumentStatus.READY,
    DocumentStatus.UPLOADED,
}


def _status_value(status) -> str:
    return status.value if hasattr(status, "value") else str(status)


@router.get("/dashboard")
async def dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    usage = await ensure_quota(db, user.id, 0)
    await file_unfiled_into_default(db, user.id)
    await db.commit()

    file_rows = (
        await db.scalars(
            select(Document)
            .where(
                Document.user_id == user.id,
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
            )
            .order_by(Document.created_at.desc())
        )
    ).all()
    ready = processing = failed = 0
    images = pdfs = other = 0
    downloads = shares = 0
    processing_values = {item.value for item in PROCESSING_STATUSES}
    ready_values = {item.value for item in READY_STATUSES}
    for doc in file_rows:
        value = _status_value(doc.status)
        if value in ready_values:
            ready += 1
        elif value in processing_values:
            processing += 1
        else:
            failed += 1
        mime = (doc.mime_type or "").lower()
        name = (doc.original_filename or "").lower()
        if mime.startswith("image/") or name.endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff", ".avif")
        ):
            images += 1
        elif "pdf" in mime or name.endswith(".pdf"):
            pdfs += 1
        else:
            other += 1
        downloads += getattr(doc, "download_count", 0) or 0
        shares += getattr(doc, "share_count", 0) or 0
    total = len(file_rows)

    cols = (
        await db.scalars(select(Collection).where(Collection.user_id == user.id).order_by(Collection.name))
    ).all()
    parents = {col.id: col.parent_id for col in cols}
    docs_by_col = await document_ids_for_collections(db, [col.id for col in cols])
    filed: set[str] = set()
    folders = []
    for col in cols:
        ids = set(docs_by_col.get(col.id, []))
        filed.update(ids)
        if col.parent_id:
            continue
        folders.append(
            {
                "id": col.id,
                "name": col.name,
                "file_count": len(ids),
                "child_count": len(descendants_of(col.id, parents)),
            }
        )
    folders.sort(key=lambda item: (-item["file_count"], item["name"].lower()))
    unfiled = sum(1 for doc in file_rows if str(doc.id) not in filed)
    recent = [
        {
            "id": doc.id,
            "title": doc.title,
            "original_filename": doc.original_filename,
            "mime_type": doc.mime_type,
            "size_bytes": doc.size_bytes,
            "created_at": doc.created_at,
        }
        for doc in file_rows[:5]
    ]

    quota = usage.quota_bytes or 104_857_600
    used = sum(int(doc.size_bytes or 0) for doc in file_rows)
    if (usage.used_bytes or 0) != used or (usage.file_count or 0) != total:
        usage.used_bytes = used
        usage.file_count = total
        await db.commit()
    used_percent = min(100.0, (used * 100 / quota) if quota else 0)
    today = date.today()
    health = await compute_health(db, user.id)
    expiring_items = sorted(
        (doc for doc in file_rows if doc.expiry_date and (doc.expiry_date - today).days <= 30),
        key=lambda doc: doc.expiry_date or today,
    )
    trash_count = (
        await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                Document.user_id == user.id,
                Document.trashed_at.is_not(None),
                Document.deleted_at.is_(None),
            )
        )
        or 0
    )
    return ok(
        {
            "storage": {
                "used_bytes": used,
                "quota_bytes": quota,
                "available_bytes": max(0, quota - used),
                "used_percent": round(used_percent, 2),
                "file_count": usage.file_count or total,
            },
            "documents": {
                "total": total,
                "ready": ready,
                "processing": processing,
                "failed": failed,
                "images": images,
                "pdfs": pdfs,
                "other": other,
                "unfiled": unfiled,
            },
            "activity": {"downloads": downloads, "shares": shares},
            "recent": recent,
            "collections": {
                "total": len(cols),
                "folders": folders,
            },
            "health": health,
            "expiring": {
                "soon": health.get("expiring_soon") or 0,
                "expired": health.get("expired") or 0,
                "items": [
                    {
                        "id": doc.id,
                        "title": doc.title,
                        "original_filename": doc.original_filename,
                        "mime_type": doc.mime_type,
                        "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
                    }
                    for doc in expiring_items[:5]
                ],
            },
            "trash_count": int(trash_count),
        }
    )


@router.get("/collections")
async def list_collections(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.family.service import owned_shared_collection_ids, shared_collection_payloads

    await file_unfiled_into_default(db, user.id)
    await merge_same_name_collections(db, user.id)
    await db.commit()
    rows = (
        await db.scalars(select(Collection).where(Collection.user_id == user.id).order_by(Collection.name))
    ).all()
    rows = sorted(rows, key=lambda col: (not is_default_collection(col), (col.name or "").lower()))
    docs_by_col = await document_ids_for_collections(db, [col.id for col in rows])
    family_shared = await owned_shared_collection_ids(db, user.id)
    owned = []
    for col in rows:
        data = serialize_collection(col, docs_by_col.get(col.id, []))
        data["shared"] = False
        data["shared_with_family"] = col.id in family_shared
        data["can_edit"] = True
        data["owner_name"] = None
        owned.append(data)
    incoming = await shared_collection_payloads(db, user.id)
    return ok(owned + incoming)


@router.post("/collections")
async def create_collection(
    payload: CollectionCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await assert_valid_parent(db, user.id, None, payload.parent_id)
    existing = await find_owned_collection_by_name(db, user.id, payload.name.strip(), payload.parent_id)
    if existing:
        for doc_id in payload.document_ids:
            await get_document_for_user(db, user.id, doc_id)
            linked = await db.scalar(
                select(CollectionDocument).where(
                    CollectionDocument.collection_id == existing.id,
                    CollectionDocument.document_id == doc_id,
                )
            )
            if not linked:
                db.add(CollectionDocument(collection_id=existing.id, document_id=doc_id))
        await db.commit()
        docs = await document_ids_for_collections(db, [existing.id])
        return ok(serialize_collection(existing, docs.get(existing.id, [])))
    col = Collection(
        user_id=user.id,
        name=payload.name.strip(),
        description=payload.description,
        parent_id=payload.parent_id,
        ai_context=payload.ai_context,
        extra=payload.metadata or {},
        goal_key=payload.goal_key,
    )
    db.add(col)
    await db.flush()
    for doc_id in payload.document_ids:
        await get_document_for_user(db, user.id, doc_id)
        db.add(CollectionDocument(collection_id=col.id, document_id=doc_id))
    await db.commit()
    await db.refresh(col)
    return ok(serialize_collection(col, payload.document_ids))


@router.patch("/collections/{collection_id}")
async def update_collection(
    collection_id: str,
    payload: CollectionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = await owned_collection(db, user.id, collection_id)
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        parent_id = data["parent_id"]
        if parent_id == collection_id:
            from app.exceptions import AppError

            raise AppError("COLLECTION_CYCLE", "A collection cannot be nested under itself", 400)
        await assert_valid_parent(db, user.id, collection_id, parent_id)
        col.parent_id = parent_id
    if "name" in data and data["name"]:
        col.name = data["name"].strip()
    if "description" in data:
        col.description = data["description"]
    if "ai_context" in data:
        col.ai_context = data["ai_context"]
    if "metadata" in data:
        col.extra = data["metadata"] or {}
    if "goal_key" in data:
        col.goal_key = data["goal_key"]
    await db.commit()
    docs = await document_ids_for_collections(db, [col.id])
    return ok(serialize_collection(col, docs.get(col.id, [])))


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await delete_owned_collection(db, user.id, collection_id)
    await db.commit()
    return ok({"deleted": True, "id": collection_id})


@router.get("/collections/{collection_id}/files")
async def collection_files(
    collection_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    from app.family.service import accessible_collection

    await accessible_collection(db, user.id, collection_id)
    docs_by_col = await document_ids_for_collections(db, [collection_id])
    ids = docs_by_col.get(collection_id, [])
    if not ids:
        return ok([])
    rows = (
        await db.scalars(
            select(Document).where(
                Document.id.in_(ids),
                Document.user_id == user.id,
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
            )
        )
    ).all()
    order = {doc_id: index for index, doc_id in enumerate(ids)}
    rows = sorted(rows, key=lambda doc: order.get(doc.id, 99))
    return ok([serialize_tree_file(doc) for doc in rows])


@router.post("/collections/{collection_id}/documents/{document_id}")
async def add_to_collection(
    collection_id: str,
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await owned_collection(db, user.id, collection_id)
    await get_document_for_user(db, user.id, document_id)
    existing = await db.scalar(
        select(CollectionDocument).where(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == document_id,
        )
    )
    if not existing:
        db.add(CollectionDocument(collection_id=collection_id, document_id=document_id))
        await db.commit()
    return ok({"added": True})


@router.delete("/collections/{collection_id}/documents/{document_id}")
async def remove_from_collection(
    collection_id: str,
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await owned_collection(db, user.id, collection_id)
    await db.execute(
        delete(CollectionDocument).where(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == document_id,
        )
    )
    await assign_to_default_if_unfiled(db, user.id, document_id)
    await db.commit()
    return ok({"removed": True})


@router.get("/reminders")
async def list_reminders(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(select(Reminder).where(Reminder.user_id == user.id).order_by(Reminder.fire_at.asc()))
    ).all()
    return ok([reminder_view(r) for r in rows])


@router.post("/reminders")
async def create_reminder(
    payload: ReminderCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    fire_at = payload.fire_at or datetime.now(UTC) + timedelta(days=payload.offset_days)
    reminder = Reminder(
        user_id=user.id,
        document_id=payload.document_id,
        collection_id=payload.collection_id,
        title=payload.title,
        offset_days=payload.offset_days,
        fire_at=fire_at,
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return ok({"id": reminder.id, "fire_at": reminder.fire_at})


@router.delete("/reminders/{reminder_id}")
async def delete_reminder(
    reminder_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    reminder = await db.get(Reminder, reminder_id)
    if not reminder or reminder.user_id != user.id:
        raise NotFoundError("REMINDER_NOT_FOUND", "Reminder not found")
    await cancel_reminder(reminder)
    await db.commit()
    await db.refresh(reminder)
    return ok(reminder_view(reminder))


@router.get("/tasks")
async def list_tasks(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Task).where(Task.user_id == user.id))).all()
    return ok(
        [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status.value,
                "due_at": t.due_at,
                "completed_at": t.completed_at,
            }
            for t in rows
        ]
    )


@router.post("/tasks")
async def create_task(payload: TaskCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    task = Task(
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        collection_id=payload.collection_id,
        document_id=payload.document_id,
        due_at=payload.due_at,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return ok({"id": task.id, "title": task.title, "status": task.status.value})


@router.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        return ok({"completed": False})
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now(UTC)
    await db.commit()
    return ok({"completed": True})
