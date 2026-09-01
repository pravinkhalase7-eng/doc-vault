from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.collections.service import descendants_of, matching_collections, parent_map
from app.config import get_settings
from app.documents.processing import local_embedding
from app.models.collection import CollectionDocument
from app.models.document import Category, Document, DocumentChunk
from app.search.query import lists_all_collections, query_terms

settings = get_settings()


async def hybrid_search(db: AsyncSession, user_id: str, query: str, limit: int = 12) -> list[dict]:
    if lists_all_collections(query):
        return []
    hits: dict[str, dict] = {}
    matched = await matching_collections(db, user_id, query)
    if matched:
        await _fill_collection_hits(db, user_id, matched, hits)
        ranked = sorted(hits.values(), key=lambda item: item["score"], reverse=True)
        return ranked[:limit]

    terms = query_terms(query)
    keyword_clauses = []
    for term in terms:
        like = f"%{term}%"
        keyword_clauses.extend(
            [
                Document.title.ilike(like),
                Document.original_filename.ilike(like),
                Document.ocr_text.ilike(like),
                Document.ai_classification.ilike(like),
                Document.related_person.ilike(like),
                Document.description.ilike(like),
            ]
        )
    keyword_rows = []
    if keyword_clauses:
        keyword_rows = (
            await db.scalars(
                select(Document).where(
                    Document.user_id == user_id,
                    Document.deleted_at.is_(None),
                    Document.trashed_at.is_(None),
                    Document.exclude_from_ai.is_(False),
                    or_(*keyword_clauses),
                ).limit(limit)
            )
        ).all()
    for doc in keyword_rows:
        hits[doc.id] = {
            "document_id": doc.id,
            "title": doc.title,
            "page": 1,
            "score": 0.7,
            "source": "keyword",
            "snippet": (doc.ocr_text or doc.title)[:240],
        }
    await _apply_category_hits(db, user_id, terms, hits)
    if not hits and not terms:
        await _apply_vault_fallback(db, user_id, query, hits)
    if hits:
        embedding = local_embedding(query, settings.embedding_dimensions)
        try:
            vector_literal = "[" + ",".join(str(x) for x in embedding) + "]"
            result = await db.execute(
                text(
                    """
                    SELECT c.document_id, c.page, c.text,
                           1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
                    FROM document_chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.user_id = :user_id
                      AND d.deleted_at IS NULL
                      AND d.trashed_at IS NULL
                      AND d.exclude_from_ai = false
                      AND c.embedding IS NOT NULL
                    ORDER BY c.embedding <=> CAST(:embedding AS vector)
                    LIMIT :limit
                    """
                ),
                {"embedding": vector_literal, "user_id": user_id, "limit": limit},
            )
            for row in result.mappings():
                current = hits.get(str(row["document_id"]))
                if not current:
                    continue
                score = float(row["score"] or 0)
                if score > current["score"]:
                    current["score"] = score
                    current["source"] = "hybrid"
                    current["page"] = row["page"]
                    current["snippet"] = (row["text"] or current.get("snippet") or "")[:240]
        except Exception:
            pass
    ranked = sorted(hits.values(), key=lambda item: item["score"], reverse=True)
    return ranked[:limit]


async def _fill_collection_hits(
    db: AsyncSession, user_id: str, matched: list, hits: dict[str, dict]
) -> None:
    if not matched:
        return
    parents = await parent_map(db, user_id)
    collection_ids: set[str] = set()
    for col in matched:
        collection_ids.add(col.id)
        collection_ids |= descendants_of(col.id, parents)
    if not collection_ids:
        return
    rows = (
        await db.execute(
            select(CollectionDocument.document_id, Document.title, Document.ocr_text).join(
                Document, Document.id == CollectionDocument.document_id
            ).where(
                CollectionDocument.collection_id.in_(collection_ids),
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
                Document.exclude_from_ai.is_(False),
            )
        )
    ).all()
    names = [col.name for col in matched if getattr(col, "name", None)]
    note = next((col.ai_context or col.description or col.name for col in matched), "collection")
    for document_id, title, ocr_text in rows:
        doc_id = str(document_id)
        snippet = (title or ocr_text or note or "")[:240]
        hits[doc_id] = {
            "document_id": doc_id,
            "title": title or "Document",
            "page": 1,
            "score": 0.92,
            "source": "collection",
            "snippet": snippet,
            "collections": names,
        }


async def _apply_category_hits(
    db: AsyncSession, user_id: str, terms: list[str], hits: dict[str, dict]
) -> None:
    if not terms:
        return
    lowered = {term.lower() for term in terms}
    categories = (
        await db.scalars(select(Category).where(Category.is_system.is_(True), Category.deleted_at.is_(None)))
    ).all()
    matched_ids = [cat.id for cat in categories if cat.name and cat.name.lower() in lowered]
    if not matched_ids:
        return
    rows = (
        await db.scalars(
            select(Document).where(
                Document.user_id == user_id,
                Document.category_id.in_(matched_ids),
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
                Document.exclude_from_ai.is_(False),
            )
        )
    ).all()
    for doc in rows:
        if doc.id in hits:
            continue
        hits[doc.id] = {
            "document_id": doc.id,
            "title": doc.title,
            "page": 1,
            "score": 0.78,
            "source": "category",
            "snippet": (doc.ocr_text or doc.title)[:240],
        }


async def _apply_vault_fallback(
    db: AsyncSession, user_id: str, query: str, hits: dict[str, dict]
) -> None:
    lowered = (query or "").lower()
    if not any(word in lowered for word in ("show", "give", "find", "get", "list", "document", "file", "collection")):
        return
    rows = (
        await db.scalars(
            select(Document)
            .where(
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
                Document.exclude_from_ai.is_(False),
            )
            .order_by(Document.created_at.desc())
            .limit(8)
        )
    ).all()
    for doc in rows:
        hits[doc.id] = {
            "document_id": doc.id,
            "title": doc.title,
            "page": 1,
            "score": 0.45,
            "source": "vault",
            "snippet": (doc.ocr_text or doc.title)[:240],
        }
