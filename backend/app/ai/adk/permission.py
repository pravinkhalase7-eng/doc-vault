"""Permission layer between ADK tools and the database. Gemini never queries Postgres."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.service import get_document_for_user
from app.exceptions import ForbiddenError
from app.models.document import Document
from app.models.enums import SensitivityLevel
from app.models.user import User


@dataclass
class ToolContext:
    db: AsyncSession
    user: User
    operation: str


class ToolPermissionService:
    async def assert_user(self, ctx: ToolContext, user_id: str) -> None:
        if ctx.user.id != user_id:
            raise ForbiddenError("TOOL_USER_MISMATCH", "Tool called with a different user id")

    async def document(self, ctx: ToolContext, document_id: str) -> Document:
        doc = await get_document_for_user(ctx.db, ctx.user.id, document_id)
        if doc.exclude_from_ai:
            raise ForbiddenError("AI_EXCLUDED", "This document is excluded from AI")
        if doc.sensitivity == SensitivityLevel.HIGHLY_SENSITIVE:
            prefs = ctx.user.preferences
            if ctx.operation in {"summarize", "external_reason"} and not (
                prefs and prefs.allow_highly_sensitive_external
            ):
                raise ForbiddenError("HIGHLY_SENSITIVE", "Highly sensitive documents stay local")
        return doc


permissions = ToolPermissionService()
