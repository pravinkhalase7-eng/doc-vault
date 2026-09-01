"""Build the smallest possible structured context. Never send entire vaults or PDFs."""

from datetime import date

from app.ai.privacy_gateway import minimize_text
from app.models.document import Document, DocumentMetadata


def build_context(
    question: str,
    documents: list[Document],
    metadata: list[DocumentMetadata],
    *,
    language: str = "en",
    collections_by_doc: dict[str, list[dict]] | None = None,
    matched_collections: list[dict] | None = None,
) -> dict:
    meta_by_doc: dict[str, list[dict]] = {}
    for item in metadata:
        meta_by_doc.setdefault(item.document_id, []).append(
            {
                "field": item.field_name,
                "value": item.value,
                "confidence": item.confidence,
                "page": item.page,
                "verified": item.verification_status.value
                if hasattr(item.verification_status, "value")
                else item.verification_status,
            }
        )
    by_doc = collections_by_doc or {}
    records = []
    seen_collections: list[dict] = []
    seen_ids: set[str] = set()
    for doc in documents[:12]:
        snippet = minimize_text(doc.ocr_text or "", 400)
        linked = by_doc.get(doc.id, [])
        for col in linked:
            if col.get("id") and col["id"] not in seen_ids:
                seen_ids.add(col["id"])
                seen_collections.append(col)
        records.append(
            {
                "id": doc.id,
                "title": doc.title,
                "type": doc.ai_classification,
                "category_id": doc.category_id,
                "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
                "issue_date": doc.issue_date.isoformat() if doc.issue_date else None,
                "related_person": doc.related_person,
                "page_count": doc.page_count,
                "metadata": meta_by_doc.get(doc.id, []),
                "collections": linked,
                "snippet": snippet,
            }
        )
    return {
        "question": question,
        "today": date.today().isoformat(),
        "language": language,
        "instruction": (
            "Answer only from the provided records and collection notes. If matched_collections is set, "
            "only discuss documents in those collections. If records are empty, say that collection has no documents. "
            "If the answer is not present, say "
            "\"I couldn't find this information in your documents.\" Never invent dates, "
            "numbers, or names. Cite document title and page for every factual claim. "
            "Respond in the user's language."
        ),
        "records": records,
        "collections": seen_collections,
        "matched_collections": matched_collections or seen_collections,
    }
