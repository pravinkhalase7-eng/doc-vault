import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AppError, NotFoundError
from app.models.collection import Collection, CollectionDocument
from app.models.document import Document
from app.search.query import STOPWORDS, lists_all_collections, query_terms

DEFAULT_COLLECTION_NAME = "Default"


def collection_extra(col: Collection) -> dict:
    extra = getattr(col, "extra", None)
    return extra if isinstance(extra, dict) else {}


def is_default_collection(col: Collection) -> bool:
    if collection_extra(col).get("is_default") is True:
        return True
    return (getattr(col, "name", None) or "").strip().lower() == "default" and not getattr(col, "parent_id", None)


def collection_search_blob(col: Collection) -> str:
    parts = [col.name or "", col.description or "", col.ai_context or ""]
    extra = col.extra or {}
    if isinstance(extra, dict):
        for key, value in extra.items():
            parts.append(str(key))
            parts.append(str(value))
    return " ".join(parts).strip()


def serialize_collection(col: Collection, document_ids: list[str] | None = None) -> dict:
    extra = collection_extra(col)
    return {
        "id": col.id,
        "name": col.name,
        "description": col.description,
        "parent_id": col.parent_id,
        "ai_context": col.ai_context,
        "metadata": extra,
        "goal_key": col.goal_key,
        "is_default": is_default_collection(col),
        "document_ids": document_ids or [],
    }


async def owned_collection(db: AsyncSession, user_id: str, collection_id: str) -> Collection:
    col = await db.get(Collection, collection_id)
    if not col or col.user_id != user_id:
        raise NotFoundError("COLLECTION_NOT_FOUND", "Collection not found")
    return col


async def ensure_default_collection(db: AsyncSession, user_id: str) -> Collection:
    rows = (
        await db.scalars(
            select(Collection).where(Collection.user_id == user_id, Collection.parent_id.is_(None))
        )
    ).all()
    marked = next((col for col in rows if collection_extra(col).get("is_default") is True), None)
    if marked:
        return marked
    named = next((col for col in rows if (col.name or "").strip().lower() == "default"), None)
    if named:
        named.extra = {**collection_extra(named), "is_default": True}
        await db.flush()
        return named
    col = Collection(user_id=user_id, name=DEFAULT_COLLECTION_NAME, extra={"is_default": True})
    db.add(col)
    await db.flush()
    return col


async def assign_to_default_if_unfiled(db: AsyncSession, user_id: str, document_id: str) -> Collection:
    existing = await db.scalar(select(CollectionDocument).where(CollectionDocument.document_id == document_id))
    default = await ensure_default_collection(db, user_id)
    if existing:
        return default
    db.add(CollectionDocument(collection_id=default.id, document_id=document_id))
    await db.flush()
    return default


async def file_unfiled_into_default(db: AsyncSession, user_id: str) -> Collection:
    default = await ensure_default_collection(db, user_id)
    filed_ids = (
        select(CollectionDocument.document_id)
        .join(Collection, Collection.id == CollectionDocument.collection_id)
        .where(Collection.user_id == user_id)
    )
    unfiled = (
        await db.scalars(
            select(Document.id).where(
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
                ~Document.id.in_(filed_ids),
            )
        )
    ).all()
    for doc_id in unfiled:
        db.add(CollectionDocument(collection_id=default.id, document_id=str(doc_id)))
    if unfiled:
        await db.flush()
    return default


async def move_document_to_collection(
    db: AsyncSession, user_id: str, document_id: str, collection_id: str
) -> Collection:
    from app.documents.service import get_document_for_user

    await get_document_for_user(db, user_id, document_id, require_owner=True)
    col = await owned_collection(db, user_id, collection_id)
    await db.execute(delete(CollectionDocument).where(CollectionDocument.document_id == document_id))
    db.add(CollectionDocument(collection_id=col.id, document_id=document_id))
    await db.flush()
    return col


async def place_uploaded_document(
    db: AsyncSession, user_id: str, document_id: str, collection_id: str | None
) -> Collection:
    if collection_id:
        return await move_document_to_collection(db, user_id, document_id, collection_id)
    return await assign_to_default_if_unfiled(db, user_id, document_id)


async def delete_owned_collection(db: AsyncSession, user_id: str, collection_id: str) -> Collection:
    col = await owned_collection(db, user_id, collection_id)
    if is_default_collection(col):
        raise AppError("DEFAULT_COLLECTION", "The Default collection can't be deleted", 400)
    children = (
        await db.scalars(select(Collection).where(Collection.parent_id == collection_id, Collection.user_id == user_id))
    ).all()
    for child in children:
        child.parent_id = col.parent_id
    await db.delete(col)
    await db.flush()
    return col


async def parent_map(db: AsyncSession, user_id: str) -> dict[str, str | None]:
    rows = (await db.scalars(select(Collection).where(Collection.user_id == user_id))).all()
    return {row.id: row.parent_id for row in rows}


def would_cycle(collection_id: str, new_parent_id: str | None, parents: dict[str, str | None]) -> bool:
    current = new_parent_id
    seen: set[str] = set()
    while current:
        if current == collection_id:
            return True
        if current in seen:
            return True
        seen.add(current)
        current = parents.get(current)
    return False


def descendants_of(collection_id: str, parents: dict[str, str | None]) -> set[str]:
    children: dict[str, list[str]] = {}
    for cid, parent in parents.items():
        if parent:
            children.setdefault(parent, []).append(cid)
    found: set[str] = set()
    stack = list(children.get(collection_id, []))
    while stack:
        node = stack.pop()
        if node in found:
            continue
        found.add(node)
        stack.extend(children.get(node, []))
    return found


async def document_ids_for_collections(db: AsyncSession, collection_ids: list[str]) -> dict[str, list[str]]:
    if not collection_ids:
        return {}
    rows = (
        await db.execute(
            select(CollectionDocument.collection_id, CollectionDocument.document_id)
            .join(Document, Document.id == CollectionDocument.document_id)
            .where(
                CollectionDocument.collection_id.in_(collection_ids),
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
            )
        )
    ).all()
    grouped: dict[str, list[str]] = {cid: [] for cid in collection_ids}
    for collection_id, document_id in rows:
        grouped.setdefault(str(collection_id), []).append(str(document_id))
    return grouped


async def collections_for_documents(
    db: AsyncSession, user_id: str, document_ids: list[str]
) -> dict[str, list[dict]]:
    if not document_ids:
        return {}
    rows = (
        await db.execute(
            select(CollectionDocument.document_id, Collection).join(
                Collection, Collection.id == CollectionDocument.collection_id
            ).where(
                CollectionDocument.document_id.in_(document_ids),
                Collection.user_id == user_id,
            )
        )
    ).all()
    grouped: dict[str, list[dict]] = {}
    for document_id, col in rows:
        grouped.setdefault(str(document_id), []).append(
            {
                "id": col.id,
                "name": col.name,
                "ai_context": col.ai_context,
                "metadata": col.extra if isinstance(col.extra, dict) else {},
            }
        )
    return grouped


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 2:
        return 99
    prev = list(range(len(right) + 1))
    for i, char_l in enumerate(left, 1):
        curr = [i]
        for j, char_r in enumerate(right, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (char_l != char_r)))
        prev = curr
    return prev[-1]


def _close_name_match(term: str, name: str) -> bool:
    if not term or not name:
        return False
    if term == name or (len(term) >= 4 and name.startswith(term)):
        return True
    if min(len(term), len(name)) >= 4 and _edit_distance(term, name) <= 1:
        return True
    for part in re.findall(r"[a-z0-9]{3,}", name):
        if part in STOPWORDS:
            continue
        if term == part:
            return True
        if min(len(term), len(part)) >= 4 and _edit_distance(term, part) <= 1:
            return True
    return False


def collection_matches_query(col: Collection, query: str) -> bool:
    question = (query or "").lower()
    name = (col.name or "").strip().lower()
    if not name:
        return False
    if re.search(rf"\b{re.escape(name)}\b", question):
        return True
    for part in re.findall(r"[a-z0-9]{3,}", name):
        if part in STOPWORDS:
            continue
        if re.search(rf"\b{re.escape(part)}\b", question):
            return True
    terms = query_terms(query)
    if name in terms:
        return True
    return any(_close_name_match(term, name) for term in terms)


async def matching_collections(db: AsyncSession, user_id: str, query: str) -> list[Collection]:
    if lists_all_collections(query) or len((query or "").strip()) < 2:
        return []
    rows = (await db.scalars(select(Collection).where(Collection.user_id == user_id))).all()
    return [col for col in rows if collection_matches_query(col, query)]


def serialize_tree_file(doc: Document) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "original_filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
    }


async def collection_tree(db: AsyncSession, user_id: str) -> list[dict]:
    rows = (
        await db.scalars(select(Collection).where(Collection.user_id == user_id).order_by(Collection.name))
    ).all()
    if not rows:
        return []
    docs_by_col = await document_ids_for_collections(db, [col.id for col in rows])
    doc_ids = list({doc_id for ids in docs_by_col.values() for doc_id in ids})
    files_by_id: dict[str, Document] = {}
    if doc_ids:
        files = (
            await db.scalars(
                select(Document).where(
                    Document.id.in_(doc_ids),
                    Document.user_id == user_id,
                    Document.deleted_at.is_(None),
                    Document.trashed_at.is_(None),
                )
            )
        ).all()
        files_by_id = {doc.id: doc for doc in files}

    children: dict[str | None, list[Collection]] = {}
    for col in rows:
        children.setdefault(col.parent_id, []).append(col)

    def node(col: Collection) -> dict:
        documents = [
            serialize_tree_file(doc)
            for doc_id in docs_by_col.get(col.id, [])
            if (doc := files_by_id.get(doc_id))
        ]
        nested = [node(child) for child in children.get(col.id, [])]
        return {
            "id": col.id,
            "name": col.name or "Untitled",
            "document_count": len(documents),
            "documents": documents,
            "children": nested,
        }

    return [node(col) for col in children.get(None, [])]


async def assert_valid_parent(
    db: AsyncSession, user_id: str, collection_id: str | None, parent_id: str | None
) -> None:
    if not parent_id:
        return
    parent = await owned_collection(db, user_id, parent_id)
    if collection_id:
        parents = await parent_map(db, user_id)
        if would_cycle(collection_id, parent.id, parents):
            raise AppError("COLLECTION_CYCLE", "A collection cannot be nested under itself", 400)
        depth = 0
        current = parent.id
        while current and depth < 8:
            depth += 1
            current = parents.get(current)
        if depth >= 6:
            raise AppError("COLLECTION_TOO_DEEP", "Collections can only nest 6 levels deep", 400)
