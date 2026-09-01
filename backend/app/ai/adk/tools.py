"""Controlled ADK tools. All database access goes through services + permissions."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.adk.permission import ToolContext, permissions
from app.documents.service import list_documents, serialize_document
from app.exceptions import AppError
from app.models.collection import Collection, CollectionDocument, Reminder, Task
from app.models.document import Document, DocumentMetadata
from app.models.enums import TaskStatus
from app.search.hybrid import hybrid_search


def _ok(data: Any) -> dict:
    return {"status": "success", "data": data}


def _err(message: str) -> dict:
    return {"status": "error", "error_message": message}


class VaultTools:
    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx

    async def search_documents(self, query: str) -> dict:
        rows, _ = await list_documents(self.ctx.db, self.ctx.user.id, q=query, limit=20)
        return _ok([serialize_document(d) for d in rows if not d.exclude_from_ai])

    async def search_semantic_documents(self, query: str) -> dict:
        hits = await hybrid_search(self.ctx.db, self.ctx.user.id, query)
        return _ok(hits)

    async def search_collections(self, query: str) -> dict:
        from app.collections.service import matching_collections, serialize_collection

        rows = await matching_collections(self.ctx.db, self.ctx.user.id, query)
        return _ok([serialize_collection(col) for col in rows])

    async def list_collections(self) -> dict:
        from app.collections.service import serialize_collection

        rows = (
            await self.ctx.db.scalars(select(Collection).where(Collection.user_id == self.ctx.user.id))
        ).all()
        return _ok([serialize_collection(col) for col in rows])

    async def get_document_metadata(self, document_id: str) -> dict:
        doc = await permissions.document(self.ctx, document_id)
        fields = (
            await self.ctx.db.scalars(
                select(DocumentMetadata).where(DocumentMetadata.document_id == doc.id)
            )
        ).all()
        return _ok(
            {
                "document": serialize_document(doc),
                "fields": [
                    {
                        "field": f.field_name,
                        "value": f.value,
                        "confidence": f.confidence,
                        "page": f.page,
                        "verified": f.verification_status.value
                        if hasattr(f.verification_status, "value")
                        else f.verification_status,
                    }
                    for f in fields
                ],
            }
        )

    async def find_expiring_documents(self, days: int = 30) -> dict:
        until = date.today() + timedelta(days=days)
        rows = (
            await self.ctx.db.scalars(
                select(Document).where(
                    Document.user_id == self.ctx.user.id,
                    Document.deleted_at.is_(None),
                    Document.trashed_at.is_(None),
                    Document.exclude_from_ai.is_(False),
                    Document.expiry_date.is_not(None),
                    Document.expiry_date <= until,
                )
            )
        ).all()
        return _ok(
            [
                {"id": d.id, "title": d.title, "expiry_date": d.expiry_date.isoformat()}
                for d in rows
            ]
        )

    async def find_related_documents(self, document_id: str) -> dict:
        doc = await permissions.document(self.ctx, document_id)
        rows, _ = await list_documents(self.ctx.db, self.ctx.user.id, q=doc.ai_classification or doc.title, limit=10)
        related = [serialize_document(d) for d in rows if d.id != doc.id]
        return _ok(related)

    async def find_duplicates(self) -> dict:
        from app.models.ai import AIProposal

        rows = (
            await self.ctx.db.scalars(
                select(AIProposal).where(
                    AIProposal.user_id == self.ctx.user.id,
                    AIProposal.kind == "duplicate",
                    AIProposal.status == "pending",
                )
            )
        ).all()
        return _ok([{"id": r.id, **r.payload} for r in rows])

    async def compare_documents(self, document_id_a: str, document_id_b: str) -> dict:
        a = await permissions.document(self.ctx, document_id_a)
        b = await permissions.document(self.ctx, document_id_b)
        return _ok(
            {
                "a": {"id": a.id, "title": a.title, "expiry": a.expiry_date, "type": a.ai_classification},
                "b": {"id": b.id, "title": b.title, "expiry": b.expiry_date, "type": b.ai_classification},
            }
        )

    async def create_collection(self, name: str, description: str = "", parent_id: str | None = None, ai_context: str = "") -> dict:
        col = Collection(
            user_id=self.ctx.user.id,
            name=name,
            description=description,
            parent_id=parent_id,
            ai_context=ai_context or None,
            is_ai_proposed=True,
        )
        self.ctx.db.add(col)
        await self.ctx.db.flush()
        return _ok({"id": col.id, "name": col.name, "requires_confirmation": True})

    async def add_document_to_collection(self, collection_id: str, document_id: str) -> dict:
        await permissions.document(self.ctx, document_id)
        self.ctx.db.add(CollectionDocument(collection_id=collection_id, document_id=document_id))
        await self.ctx.db.flush()
        return _ok({"collection_id": collection_id, "document_id": document_id, "requires_confirmation": True})

    async def remove_document_from_collection(self, collection_id: str, document_id: str) -> dict:
        return _ok({"collection_id": collection_id, "document_id": document_id, "requires_confirmation": True})

    async def create_reminder(self, title: str, offset_days: int = 30, document_id: str | None = None) -> dict:
        fire_at = datetime.now(UTC) + timedelta(days=max(offset_days, 0))
        if document_id:
            doc = await permissions.document(self.ctx, document_id)
            if doc.expiry_date:
                fire_at = datetime.combine(doc.expiry_date, datetime.min.time(), tzinfo=UTC) - timedelta(days=offset_days)
        reminder = Reminder(
            user_id=self.ctx.user.id,
            document_id=document_id,
            title=title,
            offset_days=offset_days,
            fire_at=fire_at,
        )
        self.ctx.db.add(reminder)
        await self.ctx.db.flush()
        return _ok({"id": reminder.id, "fire_at": fire_at.isoformat(), "requires_confirmation": True})

    async def list_reminders(self) -> dict:
        rows = (
            await self.ctx.db.scalars(select(Reminder).where(Reminder.user_id == self.ctx.user.id))
        ).all()
        return _ok([{"id": r.id, "title": r.title, "fire_at": r.fire_at.isoformat()} for r in rows])

    async def update_reminder(self, reminder_id: str, offset_days: int) -> dict:
        return _ok({"id": reminder_id, "offset_days": offset_days, "requires_confirmation": True})

    async def create_task(self, title: str) -> dict:
        task = Task(user_id=self.ctx.user.id, title=title, created_by_ai=True)
        self.ctx.db.add(task)
        await self.ctx.db.flush()
        return _ok({"id": task.id, "title": title, "requires_confirmation": True})

    async def list_tasks(self) -> dict:
        rows = (await self.ctx.db.scalars(select(Task).where(Task.user_id == self.ctx.user.id))).all()
        return _ok([{"id": t.id, "title": t.title, "status": t.status.value} for t in rows])

    async def complete_task(self, task_id: str) -> dict:
        task = await self.ctx.db.get(Task, task_id)
        if not task or task.user_id != self.ctx.user.id:
            return _err("Task not found")
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        return _ok({"id": task.id, "requires_confirmation": True})

    async def get_user_preferences(self) -> dict:
        prefs = self.ctx.user.preferences
        return _ok(
            {
                "language": prefs.language.value if prefs else "en",
                "ai_privacy_mode": prefs.ai_privacy_mode.value if prefs else "PRIVATE",
                "external_ai_enabled": bool(prefs and prefs.external_ai_enabled),
            }
        )

    async def generate_checklist(self, goal: str) -> dict:
        from app.models.enums import GOAL_CHECKLISTS

        items = GOAL_CHECKLISTS.get(goal, GOAL_CHECKLISTS.get(goal.replace(" ", "_").lower(), []))
        docs, _ = await list_documents(self.ctx.db, self.ctx.user.id, limit=200)
        titles = " ".join((d.title + " " + (d.ai_classification or "")).lower() for d in docs)
        checklist = []
        for item in items:
            present = item.lower() in titles
            evidence = next((d for d in docs if item.lower() in (d.title + " " + (d.ai_classification or "")).lower()), None)
            checklist.append(
                {
                    "item": item,
                    "present": present,
                    "document_id": evidence.id if evidence else None,
                    "document_title": evidence.title if evidence else None,
                }
            )
        return _ok({"goal": goal, "items": checklist})

    async def get_document_evidence(self, document_id: str, query: str = "") -> dict:
        doc = await permissions.document(self.ctx, document_id)
        text = doc.ocr_text or ""
        snippet = text[:400]
        if query:
            idx = text.lower().find(query.lower())
            if idx >= 0:
                snippet = text[max(0, idx - 80) : idx + 200]
        return _ok(
            {
                "document_id": doc.id,
                "document_title": doc.title,
                "page_number": 1,
                "text_reference": snippet,
            }
        )
