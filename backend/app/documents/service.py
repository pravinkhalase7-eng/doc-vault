from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, or_, select, inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.models.document import Category, Document, DocumentTag, DocumentType, Tag
from app.models.enums import DocumentStatus, SensitivityLevel, VerificationStatus
from app.models.sharing import Share
from app.models.system import StorageUsage
from app.storage.local import (
    detect_type,
    document_path,
    relative_key,
    resolve_key,
    sha256_bytes,
    write_bytes,
)

settings = get_settings()

QUOTA_WARNINGS = (80, 90, 95, 100)


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


async def get_or_create_tag(db: AsyncSession, user_id: str, name: str) -> Tag:
    slug = _slug(name)
    tag = await db.scalar(select(Tag).where(Tag.user_id == user_id, Tag.slug == slug))
    if tag:
        return tag
    tag = Tag(user_id=user_id, name=name.strip(), slug=slug)
    db.add(tag)
    await db.flush()
    return tag


async def ensure_quota(db: AsyncSession, user_id: str, incoming: int) -> StorageUsage:
    usage = await db.scalar(select(StorageUsage).where(StorageUsage.user_id == user_id))
    if not usage:
        usage = StorageUsage(user_id=user_id, used_bytes=0, quota_bytes=settings.default_storage_quota_bytes)
        db.add(usage)
        await db.flush()
    if usage.quota_bytes != settings.default_storage_quota_bytes:
        usage.quota_bytes = settings.default_storage_quota_bytes
    if incoming > 0 and usage.used_bytes + incoming > usage.quota_bytes:
        raise AppError("QUOTA_EXCEEDED", "Storage quota exceeded", 413)
    return usage


def quota_warning(usage: StorageUsage) -> int | None:
    if usage.quota_bytes <= 0:
        return None
    percent = int(usage.used_bytes * 100 / usage.quota_bytes)
    for threshold in reversed(QUOTA_WARNINGS):
        if percent >= threshold:
            return threshold
    return None


async def visible_document_ids(db: AsyncSession, user_id: str) -> set[str]:
    from app.family.service import family_document_ids

    owned = (await db.scalars(select(Document.id).where(Document.user_id == user_id, Document.deleted_at.is_(None)))).all()
    shared = (
        await db.scalars(
            select(Share.document_id).where(
                Share.grantee_id == user_id,
                Share.revoked_at.is_(None),
                Share.document_id.is_not(None),
            )
        )
    ).all()
    family = await family_document_ids(db, user_id)
    return {str(i) for i in owned if i} | {str(i) for i in shared if i} | family


async def get_document_for_user(
    db: AsyncSession,
    user_id: str,
    document_id: str,
    *,
    require_owner: bool = False,
    include_trash: bool = False,
) -> Document:
    query = select(Document).options(selectinload(Document.tags).selectinload(DocumentTag.tag)).where(Document.id == document_id)
    doc = await db.scalar(query)
    if not doc or (doc.deleted_at and not include_trash):
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Document not found")
    if doc.user_id == user_id:
        return doc
    if require_owner:
        raise ForbiddenError("NOT_OWNER", "You do not own this document")
    share = await db.scalar(
        select(Share).where(
            Share.document_id == document_id,
            Share.grantee_id == user_id,
            Share.revoked_at.is_(None),
        )
    )
    if share:
        return doc
    from app.family.service import family_document_ids

    if document_id in await family_document_ids(db, user_id):
        return doc
    raise ForbiddenError("DOCUMENT_FORBIDDEN", "You do not have access to this document")


def _tag_names(doc: Document) -> list[str]:
    try:
        if "tags" in sa_inspect(doc).unloaded:
            return []
        links = list(doc.tags or [])
    except Exception:
        links = list(getattr(doc, "tags", None) or [])
    names: list[str] = []
    for link in links:
        try:
            if "tag" in sa_inspect(link).unloaded:
                continue
        except Exception:
            pass
        tag = getattr(link, "tag", None)
        if tag is not None:
            names.append(tag.name)
    return names


def serialize_document(doc: Document) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "original_filename": doc.original_filename,
        "description": doc.description,
        "mime_type": doc.mime_type,
        "extension": doc.extension,
        "size_bytes": doc.size_bytes,
        "status": doc.status.value if hasattr(doc.status, "value") else doc.status,
        "sensitivity": doc.sensitivity.value if hasattr(doc.sensitivity, "value") else doc.sensitivity,
        "exclude_from_ai": doc.exclude_from_ai,
        "category_id": doc.category_id,
        "document_type_id": doc.document_type_id,
        "ai_classification": doc.ai_classification,
        "ai_confidence": doc.ai_confidence,
        "verification_status": doc.verification_status.value
        if hasattr(doc.verification_status, "value")
        else doc.verification_status,
        "issue_date": doc.issue_date,
        "expiry_date": doc.expiry_date,
        "related_person": doc.related_person,
        "tags": _tag_names(doc),
        "page_count": doc.page_count,
        "version": doc.version,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "trashed_at": doc.trashed_at,
        "download_count": getattr(doc, "download_count", 0) or 0,
        "share_count": getattr(doc, "share_count", 0) or 0,
        "use_count": (getattr(doc, "download_count", 0) or 0) + (getattr(doc, "share_count", 0) or 0),
        "has_thumbnail": bool(getattr(doc, "thumbnail_key", None)),
        "has_preview": bool(getattr(doc, "preview_key", None)),
    }


async def create_upload(
    db: AsyncSession,
    user_id: str,
    *,
    filename: str,
    data: bytes,
    title: str | None = None,
) -> tuple[Document, bool]:
    if len(data) > settings.max_upload_size:
        raise AppError("FILE_TOO_LARGE", "File exceeds the maximum upload size", 413)
    if not data:
        raise AppError("EMPTY_FILE", "File is empty", 400)

    mime, ext = detect_type(data, filename)
    digest = sha256_bytes(data)
    duplicate = await db.scalar(
        select(Document).where(
            Document.user_id == user_id,
            Document.sha256 == digest,
            Document.deleted_at.is_(None),
            Document.trashed_at.is_(None),
        )
    )
    usage = await ensure_quota(db, user_id, 0 if duplicate else len(data))
    if duplicate:
        display = (title or "").strip()
        if display and duplicate.title != display:
            duplicate.title = display
            await db.commit()
        return await _document_with_tags(db, duplicate.id), True

    doc_id = str(uuid4())
    path = document_path(user_id, doc_id, ext)
    await write_bytes(path, data)

    display = title or Path(filename).stem
    doc = Document(
        id=doc_id,
        user_id=user_id,
        title=display,
        original_filename=filename,
        mime_type=mime,
        extension=ext,
        size_bytes=len(data),
        sha256=digest,
        storage_key=relative_key(path),
        status=DocumentStatus.UPLOADED,
        sensitivity=SensitivityLevel.PRIVATE,
        verification_status=VerificationStatus.UNVERIFIED,
    )
    db.add(doc)
    usage.used_bytes += len(data)
    usage.file_count += 1
    await db.commit()
    return await _document_with_tags(db, doc_id), False


async def _document_with_tags(db: AsyncSession, document_id: str) -> Document:
    loaded = await db.scalar(
        select(Document)
        .options(selectinload(Document.tags).selectinload(DocumentTag.tag))
        .where(Document.id == document_id)
    )
    if loaded is None:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Document not found")
    return loaded


async def list_documents(
    db: AsyncSession,
    user_id: str,
    *,
    q: str | None = None,
    category_id: str | None = None,
    status: str | None = None,
    trash: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Document], int]:
    if trash:
        filters = [Document.user_id == user_id, Document.trashed_at.is_not(None), Document.deleted_at.is_(None)]
    else:
        visible = await visible_document_ids(db, user_id)
        if not visible:
            return [], 0
        filters = [
            Document.id.in_(visible),
            Document.trashed_at.is_(None),
            Document.deleted_at.is_(None),
        ]
    if category_id:
        filters.append(Document.category_id == category_id)
    if status:
        filters.append(Document.status == status)
    if q:
        like = f"%{q}%"
        filters.append(
            or_(
                Document.title.ilike(like),
                Document.original_filename.ilike(like),
                Document.description.ilike(like),
                Document.ocr_text.ilike(like),
                Document.related_person.ilike(like),
                Document.ai_classification.ilike(like),
            )
        )
    total = await db.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
    rows = (
        await db.scalars(
            select(Document)
            .options(selectinload(Document.tags).selectinload(DocumentTag.tag))
            .where(*filters)
            .order_by(
                (Document.download_count + Document.share_count).desc(),
                Document.updated_at.desc(),
                Document.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(rows), int(total)


async def trash_document(db: AsyncSession, user_id: str, document_id: str) -> Document:
    doc = await get_document_for_user(db, user_id, document_id, require_owner=True)
    doc.trashed_at = datetime.now(UTC)
    await db.commit()
    return doc


async def restore_document(db: AsyncSession, user_id: str, document_id: str) -> Document:
    doc = await get_document_for_user(db, user_id, document_id, require_owner=True, include_trash=True)
    doc.trashed_at = None
    await db.commit()
    return doc


async def permanently_delete(db: AsyncSession, user_id: str, document_id: str) -> None:
    doc = await get_document_for_user(db, user_id, document_id, require_owner=True, include_trash=True)
    path = resolve_key(doc.storage_key)
    usage = await db.scalar(select(StorageUsage).where(StorageUsage.user_id == user_id))
    if usage:
        usage.used_bytes = max(0, usage.used_bytes - doc.size_bytes)
        usage.file_count = max(0, usage.file_count - 1)
    doc.deleted_at = datetime.now(UTC)
    if path.exists():
        path.unlink()
    await db.commit()


async def seed_taxonomy(db: AsyncSession) -> None:
    from app.models.enums import DEFAULT_CATEGORIES, DEFAULT_DOCUMENT_TYPES, HIGHLY_SENSITIVE_TYPES

    existing = await db.scalar(select(Category).where(Category.is_system.is_(True)))
    if existing:
        return
    slug_to_id: dict[str, str] = {}
    for index, name in enumerate(DEFAULT_CATEGORIES):
        cat = Category(user_id=None, name=name, slug=_slug(name), is_system=True, sort_order=index)
        db.add(cat)
        await db.flush()
        slug_to_id[cat.slug] = cat.id
    for category_name, types in DEFAULT_DOCUMENT_TYPES.items():
        cat_id = slug_to_id.get(_slug(category_name))
        for type_name in types:
            slug = _slug(type_name)
            sensitivity = (
                SensitivityLevel.HIGHLY_SENSITIVE if slug in HIGHLY_SENSITIVE_TYPES else SensitivityLevel.PRIVATE
            )
            if slug in {"invoice", "receipt", "bank-statement", "policy"}:
                sensitivity = SensitivityLevel.SENSITIVE
            if slug in {"photo"}:
                sensitivity = SensitivityLevel.PRIVATE
            db.add(
                DocumentType(
                    user_id=None,
                    category_id=cat_id,
                    name=type_name,
                    slug=slug,
                    is_system=True,
                    default_sensitivity=sensitivity,
                )
            )
    await db.commit()
