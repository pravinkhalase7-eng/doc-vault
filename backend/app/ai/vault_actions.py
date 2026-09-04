"""Deterministic vault delete/confirm flows for Ask My Vault."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collections.service import (
    _close_name_match,
    collection_matches_query,
    delete_owned_collection,
    descendants_of,
    document_ids_for_collections,
    matching_collections,
    parent_map,
)
from app.documents.service import list_documents, trash_document
from app.models.ai import AIProposal
from app.models.collection import Collection
from app.models.document import Document
from app.models.user import User

VAULT_KINDS = (
    "ask_delete_collection",
    "ask_delete_document",
    "delete_all_files",
    "delete_collection_files",
    "delete_collection",
    "delete_document",
)
EXECUTE_KINDS = ("delete_all_files", "delete_collection_files", "delete_collection", "delete_document")
ASK_KINDS = ("ask_delete_collection", "ask_delete_document")

CONFIRM_PHRASES = {
    "yes",
    "y",
    "ok",
    "okay",
    "confirm",
    "confirmed",
    "proceed",
    "do it",
    "go ahead",
    "sure",
    "yes delete",
    "delete it",
    "delete them",
    "yes please",
    "please delete",
}
CANCEL_PHRASES = {
    "no",
    "n",
    "cancel",
    "cancelled",
    "canceled",
    "nevermind",
    "never mind",
    "don't",
    "do not",
    "stop",
    "no thanks",
    "keep them",
    "keep it",
}


@dataclass
class ParsedIntent:
    kind: str
    name: str | None = None


def clean_name(raw: str | None) -> str:
    text = re.sub(r"\s+", " ", (raw or "").strip(" .!?,;:"))
    text = re.sub(r"^(the|my|a|an|named|called)\s+", "", text, flags=re.I)
    text = re.sub(
        r"\s+(collection|folder|files|file|documents|document|docs)$",
        "",
        text,
        flags=re.I,
    )
    return text.strip()


def parse_vault_intent(message: str) -> ParsedIntent:
    text = re.sub(r"\s+", " ", (message or "").strip())
    text = re.sub(r"[.?!]+$", "", text).strip()
    lowered = text.lower()
    if not lowered:
        return ParsedIntent("none")
    if lowered in CONFIRM_PHRASES:
        return ParsedIntent("confirm")
    if lowered in CANCEL_PHRASES:
        return ParsedIntent("cancel")

    if (
        re.fullmatch(
            r"(?:please\s+)?(?:delete|remove)\s+all(?:\s+of)?(?:\s+the)?(?:\s+my)?\s+"
            r"(?:files|documents|docs)(?:\s+(?:in|from|inside)\s+(?:the\s+|my\s+)?vault)?",
            lowered,
        )
        or re.fullmatch(r"(?:please\s+)?(?:delete|remove)\s+(?:everything|all)", lowered)
        or re.fullmatch(r"(?:please\s+)?(?:empty|clear)\s+(?:the\s+|my\s+)?vault", lowered)
    ):
        return ParsedIntent("delete_all_files")

    match = re.search(
        r"(?:delete|remove)\s+all\s+(?:the\s+)?(?:files|documents|docs)\s+(?:in|from|inside|under)\s+(.+)",
        lowered,
    )
    if match:
        name = clean_name(match.group(1))
        if not name or name.lower() in {"vault", "my vault", "the vault"}:
            return ParsedIntent("delete_all_files")
        return ParsedIntent("delete_collection_files", name)
    match = re.search(
        r"(?:delete|remove)\s+all\s+(.+?)\s+(?:files|documents|docs)\b",
        lowered,
    )
    if match:
        name = clean_name(match.group(1))
        if not name or name.lower() in {"my", "the", "all", "every", "everything", "vault"}:
            return ParsedIntent("delete_all_files")
        return ParsedIntent("delete_collection_files", name)

    match = re.search(
        r"(?:delete|remove)\s+(?:the\s+)?(?:collection|folder)(?:\s+(?:named|called))?(?:\s+(.+))?",
        lowered,
    )
    if match:
        return ParsedIntent("delete_collection", clean_name(match.group(1)) or None)

    match = re.search(
        r"(?:delete|remove)\s+(?:the\s+)?(?:files?|documents?|docs)\b(?:\s+(?:named|called))?(?:\s+(.+))?",
        lowered,
    )
    if match:
        return ParsedIntent("delete_document", clean_name(match.group(1)) or None)

    match = re.match(r"(?:delete|remove)\s+(.+)", lowered)
    if match:
        name = clean_name(match.group(1))
        if name:
            return ParsedIntent("delete_named", name)

    if not re.search(r"\b(collections?|folders?)\b", lowered):
        match = re.search(
            r"^(?:show|list|give|get|find|open)\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(?:my\s+)?"
            r"(?:files?|documents?|docs)\b(?:\s+(?:named|called)\s+(.+))?$",
            lowered,
        )
        if match:
            name = clean_name(match.group(1)) if match.lastindex and match.group(1) else None
            return ParsedIntent("show_document" if name else "list_documents", name)
        match = re.search(
            r"^(?:show|open|find)\s+(?:me\s+)?(?:the\s+)?(?:file|document|doc)\s+(?:named|called)?\s*(.+)$",
            lowered,
        )
        if match:
            return ParsedIntent("show_document", clean_name(match.group(1)))
        match = re.match(r"^(?:show|open)\s+(.+)$", lowered)
        if match:
            name = clean_name(match.group(1))
            if name and name not in {"me", "this", "that"}:
                return ParsedIntent("show_document", name)
        if lowered in {"documents", "files", "docs", "my documents", "my files"}:
            return ParsedIntent("list_documents")
    return ParsedIntent("none")


def document_matches_name(doc: Any, query: str) -> bool:
    needle = clean_name(query).lower()
    if not needle or len(needle) < 2:
        return False
    title = (getattr(doc, "title", None) or "").strip().lower()
    fname = (getattr(doc, "original_filename", None) or "").strip().lower()
    stem = Path(fname).stem.lower() if fname else ""
    if needle in {title, fname, stem}:
        return True
    if title and (needle in title or title in needle):
        return True
    if stem and (needle in stem or stem in needle):
        return True
    return _close_name_match(needle, title) or _close_name_match(needle, stem)


def _bullet(names: list[str]) -> str:
    return "\n".join(f"- {name}" for name in names)


def _looks_like_name(message: str) -> bool:
    name = clean_name(message)
    words = [part for part in name.split() if part]
    if not words or len(words) > 4:
        return False
    return not re.search(r"\b(when|what|which|where|who|how|show|list|give|find|expire|expiring)\b", (message or "").lower())


def _option_bullets(pending: AIProposal) -> str:
    options = (pending.payload or {}).get("options") or []
    names = [item.get("name") or item.get("title") for item in options if item.get("name") or item.get("title")]
    return _bullet([str(name) for name in names if name])


def _match_ask_option(pending: AIProposal, name: str) -> str | None:
    needle = clean_name(name).lower()
    if not needle:
        return None
    options = (pending.payload or {}).get("options") or []
    hits: list[str] = []
    for item in options:
        label = str(item.get("name") or item.get("title") or "").strip()
        if not label:
            continue
        fake = SimpleDoc(title=label, original_filename=str(item.get("original_filename") or label))
        if pending.kind == "ask_delete_collection":
            col = SimpleCollection(name=label)
            if collection_matches_query(col, needle) or needle == label.lower():
                hits.append(label)
        elif document_matches_name(fake, needle):
            hits.append(label)
    if len(hits) == 1:
        return hits[0]
    return None


class SimpleDoc:
    def __init__(self, title: str, original_filename: str) -> None:
        self.title = title
        self.original_filename = original_filename


class SimpleCollection:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = None
        self.ai_context = None
        self.extra = {}


def _proposal_view(proposal: AIProposal, summary: str) -> dict:
    return {
        "id": proposal.id,
        "kind": proposal.kind,
        "status": proposal.status,
        "summary": summary,
        "payload": proposal.payload or {},
    }


async def handle_vault_action(
    db: AsyncSession, user: User, message: str, conversation_id: str
) -> dict | None:
    intent = parse_vault_intent(message)
    pending = await _latest_pending(db, user.id)
    if pending and intent.kind in {"confirm", "cancel"}:
        if intent.kind == "cancel":
            pending.status = "rejected"
            await db.flush()
            return {
                "answer": "Cancelled. Nothing was deleted.",
                "proposal": _proposal_view(pending, "Cancelled"),
            }
        if pending.kind in ASK_KINDS:
            return {
                "answer": _ask_again(pending),
                "proposal": _proposal_view(pending, pending.payload.get("summary") or "Waiting for a name"),
            }
        answer = await execute_vault_proposal(db, user, pending)
        return {"answer": answer, "proposal": _proposal_view(pending, answer)}

    if pending and pending.kind in ASK_KINDS and intent.kind in {"none", "delete_named", "delete_collection", "delete_document"}:
        name = intent.name or clean_name(message)
        matched = _match_ask_option(pending, name)
        if matched:
            handled = await _resolve_asked_name(db, user, pending, matched, conversation_id)
            if handled:
                return handled
        if intent.kind != "none" and name:
            handled = await _resolve_asked_name(db, user, pending, name, conversation_id)
            if handled:
                return handled
        if _looks_like_name(message):
            prompt = (
                'I could not find that collection. Which collection should I delete?'
                if pending.kind == "ask_delete_collection"
                else 'I could not find that file. Which document should I delete?'
            )
            return {
                "answer": f"{prompt}\n{_option_bullets(pending)}\n\nReply with the name.",
                "proposal": _proposal_view(pending, pending.payload.get("summary") or "Waiting for a name"),
            }
        pending.status = "rejected"
        await db.flush()

    if intent.kind == "none":
        if pending and pending.kind in EXECUTE_KINDS:
            pending.status = "rejected"
            await db.flush()
        return None

    await _cancel_pending(db, user.id)
    if intent.kind == "list_documents":
        return await _list_vault_documents(db, user)
    if intent.kind == "show_document":
        return await _show_named_document(db, user, intent.name)
    if intent.kind == "delete_all_files":
        return await _start_delete_all_files(db, user, conversation_id)
    if intent.kind == "delete_collection_files":
        return await _start_delete_collection_files(db, user, intent.name, conversation_id)
    if intent.kind == "delete_collection":
        return await _start_delete_collection(db, user, intent.name, conversation_id)
    if intent.kind == "delete_document":
        return await _start_delete_document(db, user, intent.name, conversation_id)
    if intent.kind == "delete_named":
        docs = await _matching_documents(db, user.id, intent.name or "")
        cols = await matching_collections(db, user.id, intent.name or "")
        if len(docs) == 1 and len(cols) == 1:
            return {
                "answer": (
                    f'"{intent.name}" matches both a file and a collection. '
                    f'Say "delete file {docs[0].title}" or "delete collection {cols[0].name}".'
                )
            }
        if len(docs) == 1 and not cols:
            return await _confirm_delete_document(db, user, docs[0], conversation_id)
        if len(docs) > 1:
            return await _ask_delete_document(db, user, conversation_id, docs, intent.name)
        if len(cols) == 1:
            return await _confirm_delete_collection(db, user, cols[0], conversation_id)
        if cols:
            return await _ask_delete_collection(db, user, conversation_id, cols)
        if docs:
            return await _ask_delete_document(db, user, conversation_id, docs, intent.name)
        return {
            "answer": f'I could not find a file or collection named "{intent.name}".',
        }
    return None


async def execute_vault_proposal(db: AsyncSession, user: User, proposal: AIProposal) -> str:
    if proposal.user_id != user.id:
        return "I could not complete that action."
    if proposal.status != "pending":
        return "That action was already handled."
    payload = proposal.payload or {}
    if proposal.kind in {"delete_all_files", "delete_collection_files"}:
        ids = [item for item in (payload.get("document_ids") or []) if item]
        deleted = 0
        for doc_id in ids:
            try:
                await trash_document(db, user.id, doc_id)
                deleted += 1
            except Exception:
                continue
        proposal.status = "approved"
        await db.flush()
        if proposal.kind == "delete_all_files":
            if deleted == 0:
                return "There were no files left to delete."
            label = "file" if deleted == 1 else "files"
            return f"Deleted {deleted} {label} from your vault. They’re in trash for 30 days."
        name = payload.get("collection_name") or "that collection"
        if deleted == 0:
            return f"There were no files left to delete in {name}."
        label = "file" if deleted == 1 else "files"
        return f"Deleted {deleted} {label} from {name}."
    if proposal.kind == "delete_collection":
        collection_id = payload.get("collection_id")
        name = payload.get("collection_name") or "that collection"
        if not collection_id:
            proposal.status = "rejected"
            await db.flush()
            return "I could not find that collection."
        try:
            await delete_owned_collection(db, user.id, collection_id)
        except Exception:
            proposal.status = "rejected"
            await db.flush()
            return f"I could not delete {name}."
        proposal.status = "approved"
        await db.flush()
        return f"Deleted the {name} collection. Files that were in it stay in your vault."
    if proposal.kind == "delete_document":
        document_id = payload.get("document_id")
        title = payload.get("title") or "that file"
        if not document_id:
            proposal.status = "rejected"
            await db.flush()
            return "I could not find that file."
        try:
            await trash_document(db, user.id, document_id)
        except Exception:
            proposal.status = "rejected"
            await db.flush()
            return f"I could not delete {title}."
        proposal.status = "approved"
        await db.flush()
        return f"Deleted {title}."
    proposal.status = "rejected"
    await db.flush()
    return "I could not complete that action."


async def _latest_pending(db: AsyncSession, user_id: str) -> AIProposal | None:
    return await db.scalar(
        select(AIProposal)
        .where(
            AIProposal.user_id == user_id,
            AIProposal.status == "pending",
            AIProposal.kind.in_(VAULT_KINDS),
        )
        .order_by(AIProposal.created_at.desc())
    )


async def _cancel_pending(db: AsyncSession, user_id: str) -> None:
    rows = (
        await db.scalars(
            select(AIProposal).where(
                AIProposal.user_id == user_id,
                AIProposal.status == "pending",
                AIProposal.kind.in_(VAULT_KINDS),
            )
        )
    ).all()
    for row in rows:
        row.status = "rejected"
    if rows:
        await db.flush()


async def _create_proposal(db: AsyncSession, user: User, kind: str, payload: dict) -> AIProposal:
    proposal = AIProposal(user_id=user.id, kind=kind, payload=payload, status="pending")
    db.add(proposal)
    await db.flush()
    return proposal


def _ask_again(pending: AIProposal) -> str:
    if pending.kind == "ask_delete_collection":
        return "Which collection should I delete? Reply with the collection name."
    return "Which document should I delete? Reply with the file name you saved."


async def _resolve_asked_name(
    db: AsyncSession, user: User, pending: AIProposal, name: str, conversation_id: str
) -> dict | None:
    pending.status = "rejected"
    await db.flush()
    if pending.kind == "ask_delete_collection":
        if pending.payload and pending.payload.get("files_mode"):
            return await _start_delete_collection_files(db, user, name, conversation_id)
        return await _start_delete_collection(db, user, name, conversation_id)
    return await _start_delete_document(db, user, name, conversation_id)


async def _list_vault_documents(db: AsyncSession, user: User) -> dict:
    docs, _total = await list_documents(db, user.id, limit=40)
    visible = [doc for doc in docs if not doc.trashed_at]
    if not visible:
        return {"answer": "You don't have any files yet. Tap + to save one."}
    names = [doc.title for doc in visible[:30]]
    extra = f"\n…and {len(visible) - 30} more." if len(visible) > 30 else ""
    return {
        "answer": f"Here are your files. Tap one to open it.\n{_bullet(names)}{extra}",
        "docs": visible[:24],
    }


async def _show_named_document(db: AsyncSession, user: User, name: str | None) -> dict:
    if not name:
        return await _list_vault_documents(db, user)
    matched = await _matching_documents(db, user.id, name)
    if not matched:
        return {"answer": f'I could not find a file named "{name}". Try “show documents” to see everything.'}
    if len(matched) == 1:
        doc = matched[0]
        return {"answer": f"Here's {doc.title}.", "docs": [doc]}
    return {
        "answer": f'I found {len(matched)} files matching "{name}". Tap one to open it.',
        "docs": matched[:12],
    }


async def _start_delete_all_files(db: AsyncSession, user: User, conversation_id: str) -> dict:
    docs, _ = await list_documents(db, user.id, limit=500)
    visible = [doc for doc in docs if not doc.trashed_at]
    if not visible:
        return {"answer": "You don't have any files to delete."}
    titles = [doc.title or doc.original_filename for doc in visible]
    summary = f"Delete all {len(visible)} files in your vault?"
    proposal = await _create_proposal(
        db,
        user,
        "delete_all_files",
        {
            "conversation_id": conversation_id,
            "document_ids": [doc.id for doc in visible],
            "titles": titles,
            "summary": summary,
        },
    )
    preview = _bullet(titles[:12])
    extra = f"\n…and {len(titles) - 12} more." if len(titles) > 12 else ""
    answer = (
        f"I'll move all {len(visible)} file{'s' if len(visible) != 1 else ''} in your vault to trash:\n"
        f"{preview}{extra}\n\nTap Confirm to delete them, or Cancel. You can restore from trash for 30 days."
    )
    return {"answer": answer, "proposal": _proposal_view(proposal, summary)}


async def _start_delete_collection_files(
    db: AsyncSession, user: User, name: str | None, conversation_id: str
) -> dict:
    if not name:
        cols = (await db.scalars(select(Collection).where(Collection.user_id == user.id).order_by(Collection.name))).all()
        return await _ask_delete_collection(db, user, conversation_id, list(cols), files_mode=True)
    cols = await matching_collections(db, user.id, name)
    if not cols:
        return {"answer": f'I could not find a collection named "{name}".'}
    if len(cols) > 1:
        return await _ask_delete_collection(db, user, conversation_id, cols, files_mode=True)
    return await _confirm_delete_collection_files(db, user, cols[0], conversation_id)


async def _start_delete_collection(
    db: AsyncSession, user: User, name: str | None, conversation_id: str
) -> dict:
    cols = (await db.scalars(select(Collection).where(Collection.user_id == user.id).order_by(Collection.name))).all()
    if not cols:
        return {"answer": "You don't have any collections yet."}
    if not name:
        return await _ask_delete_collection(db, user, conversation_id, list(cols))
    matched = [col for col in cols if collection_matches_query(col, name)]
    if not matched:
        return await _ask_delete_collection(
            db,
            user,
            conversation_id,
            list(cols),
            extra=f'I could not find a collection named "{name}". Which collection should I delete?',
        )
    if len(matched) > 1:
        return await _ask_delete_collection(db, user, conversation_id, matched)
    return await _confirm_delete_collection(db, user, matched[0], conversation_id)


async def _start_delete_document(
    db: AsyncSession, user: User, name: str | None, conversation_id: str
) -> dict:
    docs, _ = await list_documents(db, user.id, limit=200)
    visible = [doc for doc in docs if not doc.trashed_at]
    if not visible:
        return {"answer": "You don't have any files to delete yet."}
    if not name:
        return await _ask_delete_document(db, user, conversation_id, visible)
    matched = [doc for doc in visible if document_matches_name(doc, name)]
    if len(matched) == 1:
        return await _confirm_delete_document(db, user, matched[0], conversation_id)
    if matched:
        return await _ask_delete_document(db, user, conversation_id, matched, name)
    return await _ask_delete_document(
        db,
        user,
        conversation_id,
        visible[:12],
        extra=f'I could not find a file named "{name}". Which document should I delete?',
    )


async def _matching_documents(db: AsyncSession, user_id: str, name: str) -> list[Document]:
    docs, _ = await list_documents(db, user_id, q=name, limit=50)
    matched = [doc for doc in docs if document_matches_name(doc, name)]
    if matched:
        return matched
    return [doc for doc in docs if not doc.trashed_at][:0]


async def _collection_file_ids(db: AsyncSession, user_id: str, col: Collection) -> list[str]:
    parents = await parent_map(db, user_id)
    collection_ids = [col.id, *descendants_of(col.id, parents)]
    grouped = await document_ids_for_collections(db, collection_ids)
    ids: list[str] = []
    seen: set[str] = set()
    for cid in collection_ids:
        for doc_id in grouped.get(cid, []):
            if doc_id in seen:
                continue
            seen.add(doc_id)
            ids.append(doc_id)
    if not ids:
        return []
    rows = (
        await db.scalars(
            select(Document).where(
                Document.id.in_(ids),
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
            )
        )
    ).all()
    order = {doc_id: index for index, doc_id in enumerate(ids)}
    rows = sorted(rows, key=lambda doc: order.get(doc.id, 99))
    return [doc.id for doc in rows]


async def _documents_by_ids(db: AsyncSession, user_id: str, ids: list[str]) -> list[Document]:
    if not ids:
        return []
    rows = (
        await db.scalars(
            select(Document).where(
                Document.id.in_(ids),
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
            )
        )
    ).all()
    order = {doc_id: index for index, doc_id in enumerate(ids)}
    return sorted(rows, key=lambda doc: order.get(doc.id, 99))


async def _confirm_delete_collection_files(
    db: AsyncSession, user: User, col: Collection, conversation_id: str
) -> dict:
    ids = await _collection_file_ids(db, user.id, col)
    docs = await _documents_by_ids(db, user.id, ids)
    name = col.name or "Untitled"
    if not docs:
        return {"answer": f"{name} has no files to delete."}
    titles = [doc.title for doc in docs]
    summary = f"Delete {len(docs)} file{'s' if len(docs) != 1 else ''} in {name}?"
    proposal = await _create_proposal(
        db,
        user,
        "delete_collection_files",
        {
            "conversation_id": conversation_id,
            "collection_id": col.id,
            "collection_name": name,
            "document_ids": [doc.id for doc in docs],
            "titles": titles,
            "summary": summary,
        },
    )
    answer = (
        f"I'll delete all {len(docs)} file{'s' if len(docs) != 1 else ''} in {name}:\n"
        f"{_bullet(titles)}\n\nTap Confirm to delete them, or Cancel."
    )
    return {"answer": answer, "proposal": _proposal_view(proposal, summary)}


async def _confirm_delete_collection(
    db: AsyncSession, user: User, col: Collection, conversation_id: str
) -> dict:
    name = col.name or "Untitled"
    summary = f"Delete the {name} collection?"
    proposal = await _create_proposal(
        db,
        user,
        "delete_collection",
        {
            "conversation_id": conversation_id,
            "collection_id": col.id,
            "collection_name": name,
            "summary": summary,
        },
    )
    answer = (
        f"I'll delete the {name} collection. Files inside it stay in your vault.\n\n"
        "Tap Confirm to delete it, or Cancel."
    )
    return {"answer": answer, "proposal": _proposal_view(proposal, summary)}


async def _confirm_delete_document(
    db: AsyncSession, user: User, doc: Document, conversation_id: str
) -> dict:
    title = doc.title or doc.original_filename or "that file"
    summary = f"Delete {title}?"
    proposal = await _create_proposal(
        db,
        user,
        "delete_document",
        {
            "conversation_id": conversation_id,
            "document_id": doc.id,
            "title": title,
            "summary": summary,
        },
    )
    answer = f"I'll delete {title}.\n\nTap Confirm to delete it, or Cancel."
    return {"answer": answer, "proposal": _proposal_view(proposal, summary)}


async def _ask_delete_collection(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    cols: list[Collection],
    extra: str | None = None,
    files_mode: bool = False,
) -> dict:
    names = [col.name or "Untitled" for col in cols]
    summary = "Which collection should I delete the files from?" if files_mode else "Which collection should I delete?"
    proposal = await _create_proposal(
        db,
        user,
        "ask_delete_collection",
        {
            "conversation_id": conversation_id,
            "files_mode": files_mode,
            "options": [{"id": col.id, "name": col.name or "Untitled"} for col in cols],
            "summary": summary,
        },
    )
    prompt = extra or summary
    answer = f"{prompt}\n{_bullet(names)}\n\nReply with the collection name."
    return {"answer": answer, "proposal": _proposal_view(proposal, summary)}


async def _ask_delete_document(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    docs: list[Document],
    name: str | None = None,
    extra: str | None = None,
) -> dict:
    titles = [doc.title or doc.original_filename for doc in docs[:12]]
    summary = "Which document should I delete?"
    proposal = await _create_proposal(
        db,
        user,
        "ask_delete_document",
        {
            "conversation_id": conversation_id,
            "query": name,
            "options": [{"id": doc.id, "title": doc.title, "original_filename": doc.original_filename} for doc in docs[:12]],
            "summary": summary,
        },
    )
    prompt = extra or summary
    answer = (
        f"{prompt}\n{_bullet(titles)}\n\n"
        "Reply with the file name you saved when you uploaded it."
    )
    return {"answer": answer, "proposal": _proposal_view(proposal, summary)}
