from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adk.root_agent import run_vault_agent
from app.auth.service import get_current_user
from app.database import get_db
from app.models.ai import AIAuditLog, AIConversation, AIFeedback, AIMessage, AIProposal
from app.models.document import Document, DocumentChunk
from app.models.enums import GOAL_CHECKLISTS
from app.models.user import User
from app.schemas.common import ChatNoteRequest, ChatRequest, FeedbackRequest
from app.ai.adk.permission import ToolContext
from app.ai.adk.tools import VaultTools
from app.ai.vault_actions import execute_vault_proposal

router = APIRouter(prefix="/ai", tags=["ai"])


def ok(data):
    return {"success": True, "data": data}


@router.post("/chat")
async def chat(payload: ChatRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await run_vault_agent(
        db,
        user,
        payload.message,
        conversation_id=payload.conversation_id,
        language=payload.language,
        document_ids=payload.document_ids,
    )
    return ok(result)


@router.post("/notes")
async def save_note(payload: ChatNoteRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conversation = None
    if payload.conversation_id:
        conversation = await db.get(AIConversation, payload.conversation_id)
        if conversation and conversation.user_id != user.id:
            conversation = None
    if not conversation:
        conversation = AIConversation(user_id=user.id, title=payload.user_content[:80], language="en")
        db.add(conversation)
        await db.flush()
    docs = []
    if payload.document_ids:
        docs = (
            await db.scalars(
                select(Document).where(
                    Document.id.in_(payload.document_ids),
                    Document.user_id == user.id,
                    Document.deleted_at.is_(None),
                    Document.trashed_at.is_(None),
                )
            )
        ).all()
        order = {doc_id: index for index, doc_id in enumerate(payload.document_ids)}
        docs = sorted(docs, key=lambda doc: order.get(doc.id, 99))
    attachments = [
        {
            "id": doc.id,
            "title": doc.title,
            "original_filename": doc.original_filename,
            "mime_type": doc.mime_type,
            "size_bytes": doc.size_bytes,
        }
        for doc in docs
    ]
    user_msg = AIMessage(
        conversation_id=conversation.id,
        role="user",
        content=payload.user_content,
        data_access={"attachments": attachments},
    )
    assistant_msg = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=payload.assistant_content,
        data_access={"documents": [{"id": doc.id, "title": doc.title} for doc in docs], "note": True},
        model="local",
        external_ai=False,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.commit()
    return ok(
        {
            "conversation_id": conversation.id,
            "user_message_id": user_msg.id,
            "assistant_message_id": assistant_msg.id,
            "attachments": attachments,
        }
    )


@router.get("/conversations")
async def conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(AIConversation).where(AIConversation.user_id == user.id).order_by(AIConversation.created_at.desc())
        )
    ).all()
    return ok([{"id": c.id, "title": c.title, "created_at": c.created_at} for c in rows])


@router.get("/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    conv = await db.get(AIConversation, conversation_id)
    if not conv or conv.user_id != user.id:
        return ok({"messages": []})
    messages = (
        await db.scalars(select(AIMessage).where(AIMessage.conversation_id == conv.id).order_by(AIMessage.created_at))
    ).all()
    return ok(
        {
            "id": conv.id,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "evidence": m.evidence,
                    "data_access": m.data_access,
                    "external_ai": m.external_ai,
                    "model": m.model,
                    "created_at": m.created_at,
                }
                for m in messages
            ],
        }
    )


@router.delete("/conversations/{conversation_id}")
async def clear_conversation(
    conversation_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    conv = await db.get(AIConversation, conversation_id)
    if conv and conv.user_id == user.id:
        await db.delete(conv)
        await db.commit()
    return ok({"cleared": True})


@router.post("/feedback")
async def feedback(payload: FeedbackRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    db.add(AIFeedback(user_id=user.id, **payload.model_dump()))
    await db.commit()
    return ok({"stored": True})


@router.get("/proposals")
async def proposals(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(AIProposal).where(AIProposal.user_id == user.id, AIProposal.status == "pending")
        )
    ).all()
    return ok([{"id": r.id, "kind": r.kind, "payload": r.payload, "status": r.status} for r in rows])


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    proposal = await db.get(AIProposal, proposal_id)
    if not proposal or proposal.user_id != user.id:
        return ok({"approved": False})
    if proposal.kind in {
        "delete_collection_files",
        "delete_collection",
        "delete_document",
        "ask_delete_collection",
        "ask_delete_document",
    }:
        answer = await execute_vault_proposal(db, user, proposal)
        await db.commit()
        return ok({"approved": proposal.status == "approved", "answer": answer})
    proposal.status = "approved"
    if proposal.kind == "rename":
        doc = await db.get(Document, proposal.payload.get("document_id"))
        if doc and doc.user_id == user.id:
            doc.title = proposal.payload.get("suggested_title") or doc.title
    if proposal.kind == "organize":
        doc = await db.get(Document, proposal.payload.get("document_id"))
        if doc and doc.user_id == user.id:
            doc.category_id = proposal.payload.get("category_id") or doc.category_id
    await db.commit()
    return ok({"approved": True})


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    proposal = await db.get(AIProposal, proposal_id)
    if not proposal or proposal.user_id != user.id:
        return ok({"rejected": False})
    if proposal.status == "pending":
        proposal.status = "rejected"
        await db.commit()
    return ok({"rejected": True})


@router.get("/goals")
async def goals():
    return ok({"goals": list(GOAL_CHECKLISTS.keys())})


@router.post("/goals/{goal}/checklist")
async def checklist(goal: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tools = VaultTools(ToolContext(db=db, user=user, operation="checklist"))
    result = await tools.generate_checklist(goal)
    return ok(result.get("data"))
