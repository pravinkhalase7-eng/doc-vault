from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.service import get_current_user, get_file_user
from app.database import get_db
from app.documents.processing import process_document
from app.collections.service import collections_for_documents, place_uploaded_document, move_document_to_collection
from app.documents.service import (
    create_upload,
    get_document_for_user,
    get_or_create_tag,
    list_documents,
    permanently_delete,
    restore_document,
    serialize_document,
    trash_document,
)
from app.exceptions import AppError
from app.models.document import DocumentMetadata
from app.models.enums import VerificationStatus
from app.models.user import User
from app.schemas.common import ConfirmMetadataRequest, DocumentMove, DocumentUpdate
from app.storage.local import resolve_key
from app.documents.ocr import generate_reel_images

router = APIRouter(prefix="/documents", tags=["documents"])


def ok(data):
    return {"success": True, "data": data}


async def _enqueue_processing(document_id: str) -> None:
    if _celery_has_workers():
        from app.workers.tasks import process_document_task

        process_document_task.delay(document_id)
        return
    from app.database import SessionLocal

    async with SessionLocal() as db:
        await process_document(db, document_id)


def _celery_has_workers() -> bool:
    try:
        from app.workers.celery_app import celery_app

        pinged = celery_app.control.inspect(timeout=0.4).ping()
        return bool(pinged)
    except Exception:
        return False


@router.post("/upload")
async def upload(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    title: str | None = Form(None),
    collection_id: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    created = []
    target = (collection_id or "").strip() or None
    for upload_file in files:
        data = await upload_file.read()
        doc, duplicate = await create_upload(
            db, user.id, filename=upload_file.filename or "upload", data=data, title=title
        )
        if target and not duplicate:
            placed = await place_uploaded_document(db, user.id, doc.id, target)
        else:
            placed = await place_uploaded_document(db, user.id, doc.id, None)
        await db.commit()
        if not duplicate:
            background.add_task(_enqueue_processing, doc.id)
        created.append({**serialize_document(doc), "duplicate": duplicate, "collection_id": placed.id})
    return ok({"documents": created, "message": "Upload successful. Processing document..."})


@router.get("")
async def list_docs(
    q: str | None = None,
    category_id: str | None = None,
    trash: bool = False,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await list_documents(
        db, user.id, q=q, category_id=category_id, trash=trash, limit=limit, offset=offset
    )
    return ok({"items": [serialize_document(d) for d in rows], "total": total})


@router.get("/{document_id}")
async def get_doc(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await get_document_for_user(db, user.id, document_id, include_trash=True)
    fields = (await db.scalars(select(DocumentMetadata).where(DocumentMetadata.document_id == doc.id))).all()
    linked = await collections_for_documents(db, user.id, [doc.id])
    return ok(
        {
            **serialize_document(doc),
            "collections": linked.get(doc.id, []),
            "metadata_fields": [
                {
                    "id": f.id,
                    "field_name": f.field_name,
                    "value": f.value,
                    "confidence": f.confidence,
                    "page": f.page,
                    "verification_status": f.verification_status.value
                    if hasattr(f.verification_status, "value")
                    else f.verification_status,
                }
                for f in fields
            ],
        }
    )


@router.patch("/{document_id}")
async def update_doc(
    document_id: str,
    payload: DocumentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await get_document_for_user(db, user.id, document_id, require_owner=True)
    data = payload.model_dump(exclude_none=True)
    tags = data.pop("tags", None)
    for key, value in data.items():
        setattr(doc, key, value)
    if tags is not None:
        doc.tags.clear()
        for name in tags:
            tag = await get_or_create_tag(db, user.id, name)
            from app.models.document import DocumentTag

            doc.tags.append(DocumentTag(tag_id=tag.id))
    await db.commit()
    await db.refresh(doc)
    return ok(serialize_document(doc))


@router.post("/{document_id}/move")
async def move_doc(
    document_id: str,
    payload: DocumentMove,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = await move_document_to_collection(db, user.id, document_id, payload.collection_id)
    await db.commit()
    return ok({"moved": True, "collection_id": col.id, "collection_name": col.name})


@router.delete("/{document_id}")
async def delete_doc(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await trash_document(db, user.id, document_id)
    return ok({"trashed": True})


@router.post("/{document_id}/restore")
async def restore(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await restore_document(db, user.id, document_id)
    return ok(serialize_document(doc))


@router.delete("/{document_id}/permanent")
async def destroy(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await permanently_delete(db, user.id, document_id)
    return ok({"deleted": True})


@router.get("/{document_id}/download")
async def download(document_id: str, user: User = Depends(get_file_user), db: AsyncSession = Depends(get_db)):
    doc = await get_document_for_user(db, user.id, document_id)
    path = resolve_key(doc.storage_key)
    if not path.exists():
        raise AppError("FILE_MISSING", "File is not available", 404)
    doc.download_count = (doc.download_count or 0) + 1
    await db.commit()

    def iterator():
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 64)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iterator(),
        media_type=doc.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{doc.original_filename}"'},
    )


@router.get("/{document_id}/preview")
async def preview(document_id: str, user: User = Depends(get_file_user), db: AsyncSession = Depends(get_db)):
    doc = await get_document_for_user(db, user.id, document_id)
    path = resolve_key(doc.storage_key)
    if not path.exists():
        raise AppError("FILE_MISSING", "File is not available", 404)
    return FileResponse(
        path,
        media_type=doc.mime_type,
        headers={"Content-Disposition": f'inline; filename="{doc.original_filename}"'},
    )


async def _ensure_reel_jpegs(db: AsyncSession, doc) -> None:
    thumb_ok = bool(doc.thumbnail_key) and resolve_key(doc.thumbnail_key).exists()
    preview_ok = bool(doc.preview_key) and resolve_key(doc.preview_key).exists()
    if thumb_ok and preview_ok:
        return
    src = resolve_key(doc.storage_key)
    if not src.exists():
        return
    thumb, preview = await generate_reel_images(src, doc.user_id, doc.id, doc.mime_type)
    if thumb:
        doc.thumbnail_key = thumb
    if preview:
        doc.preview_key = preview
    await db.commit()
    await db.refresh(doc)


def _jpeg_response(path, filename: str):
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=86400",
        },
    )


@router.get("/{document_id}/thumbnail")
async def thumbnail(document_id: str, user: User = Depends(get_file_user), db: AsyncSession = Depends(get_db)):
    doc = await get_document_for_user(db, user.id, document_id)
    await _ensure_reel_jpegs(db, doc)
    key = doc.thumbnail_key or doc.preview_key
    if not key:
        raise AppError("FILE_MISSING", "Preview is not available", 404)
    path = resolve_key(key)
    if not path.exists():
        raise AppError("FILE_MISSING", "Preview is not available", 404)
    return _jpeg_response(path, f"{doc.id}.jpg")


@router.get("/{document_id}/reel-image")
async def reel_image(document_id: str, user: User = Depends(get_file_user), db: AsyncSession = Depends(get_db)):
    doc = await get_document_for_user(db, user.id, document_id)
    await _ensure_reel_jpegs(db, doc)
    key = doc.preview_key or doc.thumbnail_key
    if not key:
        raise AppError("FILE_MISSING", "Preview is not available", 404)
    path = resolve_key(key)
    if not path.exists():
        raise AppError("FILE_MISSING", "Preview is not available", 404)
    return _jpeg_response(path, f"{doc.id}-reel.jpg")


@router.post("/{document_id}/confirm-metadata")
async def confirm_metadata(
    document_id: str,
    payload: ConfirmMetadataRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await get_document_for_user(db, user.id, document_id, require_owner=True)
    for item in payload.fields:
        field = await db.get(DocumentMetadata, item.get("id"))
        if field and field.document_id == doc.id:
            if "value" in item:
                field.value = item["value"]
            field.verification_status = VerificationStatus.USER_CONFIRMED
            if field.field_name == "expiry_date" and field.value:
                from app.documents.processing import parse_date

                parsed = parse_date(field.value)
                if parsed:
                    doc.expiry_date = parsed
    doc.verification_status = VerificationStatus.USER_CONFIRMED
    await db.commit()
    return ok({"confirmed": True})
