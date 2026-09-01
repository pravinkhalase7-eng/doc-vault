from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIProposal
from app.models.document import Document, DocumentMetadata


async def detect_contradictions(db: AsyncSession, doc: Document) -> None:
    fields = (
        await db.scalars(select(DocumentMetadata).where(DocumentMetadata.document_id == doc.id))
    ).all()
    for field in fields:
        if not field.value or field.field_name not in {"expiry_date", "issue_date", "date_of_birth", "policy_number"}:
            continue
        others = (
            await db.scalars(
                select(DocumentMetadata).where(
                    DocumentMetadata.user_id == doc.user_id,
                    DocumentMetadata.document_id != doc.id,
                    DocumentMetadata.field_name == field.field_name,
                    DocumentMetadata.value.is_not(None),
                )
            )
        ).all()
        for other in others:
            if other.value and other.value != field.value and field.field_name == "date_of_birth":
                other_doc = await db.get(Document, other.document_id)
                db.add(
                    AIProposal(
                        user_id=doc.user_id,
                        kind="contradiction",
                        payload={
                            "field": field.field_name,
                            "document_a": {"id": doc.id, "title": doc.title, "value": field.value},
                            "document_b": {
                                "id": other.document_id,
                                "title": other_doc.title if other_doc else "Document",
                                "value": other.value,
                            },
                            "message": "Conflicting information detected. Please verify.",
                        },
                    )
                )
