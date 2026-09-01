"""DocVaultAgent: ADK root agent with specialized tool groups and a local fallback."""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adk.permission import ToolContext
from app.ai.adk.tools import VaultTools
from app.ai.context_builder import build_context
from app.ai.evidence_checker import validate_answer
from app.ai.privacy_gateway import check_ai_request
from app.ai.router import get_router
from app.ai.vault_actions import handle_vault_action
from app.collections.service import collection_tree, collections_for_documents, matching_collections
from app.config import get_settings
from app.logging import get_logger
from app.models.ai import AIConversation, AIEvidence, AIMessage
from app.models.document import Document, DocumentMetadata
from app.models.enums import AIOperation, AIPrivacyMode
from app.models.user import User
from app.search.hybrid import hybrid_search
from app.search.query import lists_all_collections
from sqlalchemy import select

log = get_logger("adk")
settings = get_settings()

ROOT_INSTRUCTION = """
You are DocVaultAgent, a private personal document assistant.
Never invent document facts. If evidence is missing, say you could not find it.
Use tools. Cite document title and page. Do not request raw files.
Destructive actions (delete, share, send) require user confirmation.
If the user wants to delete a collection, ask which collection, then confirm before deleting.
If the user wants to delete a file or document, ask for the saved file name, then confirm.
If they say delete all files in a named collection, confirm then delete those files.
Answer in the user's language.
"""


async def run_vault_agent(
    db: AsyncSession,
    user: User,
    message: str,
    *,
    conversation_id: str | None = None,
    language: str | None = None,
    document_ids: list[str] | None = None,
) -> dict:
    prefs = user.preferences
    lang = language or (prefs.language.value if prefs else "en")
    external = bool(prefs and prefs.external_ai_enabled and prefs.ai_privacy_mode != AIPrivacyMode.PRIVATE)

    attached_ids = [item for item in (document_ids or []) if item][:12]
    attached_docs = []
    if attached_ids:
        attached_docs = (
            await db.scalars(
                select(Document).where(
                    Document.id.in_(attached_ids),
                    Document.user_id == user.id,
                    Document.exclude_from_ai.is_(False),
                    Document.deleted_at.is_(None),
                    Document.trashed_at.is_(None),
                )
            )
        ).all()

    conversation = None
    if conversation_id:
        conversation = await db.get(AIConversation, conversation_id)
        if conversation and conversation.user_id != user.id:
            conversation = None
    if not conversation:
        conversation = AIConversation(user_id=user.id, title=message[:80], language=lang)
        db.add(conversation)
        await db.flush()

    listing_collections = lists_all_collections(message) and not attached_docs
    tree: list[dict] = []
    hits: list[dict] = []
    matched_cols = []
    docs: list[Document] = []
    evidence: list[dict] = []
    proposal = None
    handled = await handle_vault_action(db, user, message, conversation.id)
    if handled:
        answer = handled["answer"]
        proposal = handled.get("proposal")
        decision = {"allowed_document_ids": [], "blocked": []}
    elif listing_collections:
        tree = await collection_tree(db, user.id)
        answer = (
            "Here are your collections. Tap a folder to see what's inside."
            if tree
            else "You don't have any collections yet."
        )
        decision = {"allowed_document_ids": [], "blocked": []}
    else:
        hits = await hybrid_search(db, user.id, message, limit=8)
        matched_cols = await matching_collections(db, user.id, message)
        ids = list(dict.fromkeys([*(d.id for d in attached_docs), *[h["document_id"] for h in hits]]))
        if ids:
            docs = (
                await db.scalars(
                    select(Document).where(
                        Document.id.in_(ids),
                        Document.user_id == user.id,
                        Document.exclude_from_ai.is_(False),
                    )
                )
            ).all()
            order = {doc_id: index for index, doc_id in enumerate(ids)}
            docs = sorted(docs, key=lambda doc: order.get(doc.id, 99))

        decision = await check_ai_request(db, user, AIOperation.CHAT, list(docs), external_ai=external)
        allowed_ids = set(decision["allowed_document_ids"])
        docs = [d for d in docs if d.id in allowed_ids]
        metadata = []
        if docs:
            metadata = (
                await db.scalars(select(DocumentMetadata).where(DocumentMetadata.document_id.in_([d.id for d in docs])))
            ).all()
        context = build_context(
            message,
            list(docs),
            list(metadata),
            language=lang,
            collections_by_doc=await collections_for_documents(db, user.id, [d.id for d in docs]),
            matched_collections=[{"id": col.id, "name": col.name} for col in matched_cols],
        )

        ctx = ToolContext(db=db, user=user, operation="chat")
        tools = VaultTools(ctx)
        tool_result = None
        lowered = message.lower()
        if "expir" in lowered or "expire" in lowered:
            tool_result = await tools.find_expiring_documents(30)
            context["tool_expiring"] = tool_result.get("data")
        if "checklist" in lowered or "passport" in lowered or "missing" in lowered:
            goal = "apply_for_passport" if "passport" in lowered else "renew_insurance"
            tool_result = await tools.generate_checklist(goal)
            context["tool_checklist"] = tool_result.get("data")
        if "duplicate" in lowered:
            tool_result = await tools.find_duplicates()
            context["tool_duplicates"] = tool_result.get("data")
        router = get_router()
        answer = await router.reason(context, external_allowed=external)
        answer, evidence = validate_answer(answer, list(docs), context["records"])
    db.add(
        AIMessage(
            conversation_id=conversation.id,
            role="user",
            content=message,
            data_access={
                "attachments": [
                    {
                        "id": doc.id,
                        "title": doc.title,
                        "original_filename": doc.original_filename,
                        "mime_type": doc.mime_type,
                        "size_bytes": doc.size_bytes,
                    }
                    for doc in attached_docs
                ]
            },
        )
    )
    handled_local = bool(handled)
    data_access = {
        "used": ["collection names", "file names"] if listing_collections or handled_local else (["document type", "expiry date", "policy metadata"] if docs else []),
        "raw_document": False,
        "external_ai": False if listing_collections or handled_local else (external and settings.gemini_configured),
        "model": "local" if listing_collections or handled_local else (settings.gemini_model if external and settings.gemini_configured else "local"),
        "documents": [
            {
                "id": d.id,
                "title": d.title,
                "original_filename": d.original_filename,
                "mime_type": d.mime_type,
                "size_bytes": d.size_bytes,
            }
            for d in docs
        ],
        "blocked": decision.get("blocked") or [],
        "collection_tree": tree,
        "proposal": proposal,
    }
    assistant = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        evidence=evidence,
        model=data_access["model"],
        external_ai=data_access["external_ai"],
        data_access=data_access,
    )
    db.add(assistant)
    await db.flush()
    for item in evidence:
        db.add(
            AIEvidence(
                user_id=user.id,
                document_id=item["document_id"],
                message_id=assistant.id,
                page_number=item.get("page_number"),
                text_reference=item.get("text_reference") or "",
                ai_operation=AIOperation.CHAT,
                confidence=item.get("confidence"),
            )
        )
    await db.commit()

    if settings.gemini_configured and external:
        try:
            _try_adk_agent(message)
        except Exception:
            log.info("adk_optional_unavailable")

    return {
        "conversation_id": conversation.id,
        "message_id": assistant.id,
        "answer": answer,
        "evidence": evidence,
        "data_access": data_access,
        "external_ai": data_access["external_ai"],
        "model": data_access["model"],
        "collection_tree": tree,
    }


def _try_adk_agent(message: str) -> None:
    """Best-effort ADK wiring. Tools remain permissioned even if ADK is absent."""
    from google.adk.agents import Agent

    def ping() -> dict:
        """Health check tool that does not access user data."""
        return {"status": "success", "data": {"ok": True}}

    Agent(
        name="DocVaultAgent",
        model=settings.gemini_model,
        instruction=ROOT_INSTRUCTION,
        tools=[ping],
    )
    _ = message
