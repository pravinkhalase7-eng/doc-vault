from app.ai.adk.permission import ToolContext, ToolPermissionService
from app.exceptions import ForbiddenError
from app.models.enums import AIPrivacyMode
from app.models.user import User, UserPreference
import pytest


@pytest.mark.asyncio
async def test_tool_rejects_foreign_user_id():
    user = User(email="a@b.com", password_hash="x", full_name="A")
    user.id = "user-a"
    user.preferences = UserPreference(user_id="user-a", ai_privacy_mode=AIPrivacyMode.PRIVATE)
    svc = ToolPermissionService()
    ctx = ToolContext(db=None, user=user, operation="search")  # type: ignore[arg-type]
    with pytest.raises(ForbiddenError):
        await svc.assert_user(ctx, "user-b")
