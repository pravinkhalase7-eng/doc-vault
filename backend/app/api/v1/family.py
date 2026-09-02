from fastapi import APIRouter, Depends
from pydantic import EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import get_current_user
from app.database import get_db
from app.family.service import (
    family_snapshot,
    invite_member,
    leave_family,
    remove_member,
    share_collection_with_family,
    unshare_collection_with_family,
)
from app.models.user import User
from app.schemas.common import APIModel

router = APIRouter(prefix="/family", tags=["family"])


def ok(data):
    return {"success": True, "data": data}


class FamilyInviteRequest(APIModel):
    email: EmailStr


class FamilyShareRequest(APIModel):
    collection_id: str = Field(min_length=1)


@router.get("")
async def get_family(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    data = await family_snapshot(db, user)
    await db.commit()
    return ok(data)


@router.post("/members")
async def add_member(
    payload: FamilyInviteRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    member = await invite_member(db, user, payload.email)
    return ok(
        {
            "id": member.id,
            "email": member.email,
            "status": "joined" if member.joined_at else "pending",
        }
    )


@router.delete("/members/{member_id}")
async def delete_member(
    member_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await remove_member(db, user, member_id)
    return ok({"removed": True})


@router.post("/{family_id}/leave")
async def leave(family_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await leave_family(db, user, family_id)
    return ok({"left": True})


@router.post("/collections")
async def share_collection(
    payload: FamilyShareRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return ok(await share_collection_with_family(db, user, payload.collection_id))


@router.delete("/collections/{collection_id}")
async def unshare_collection(
    collection_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await unshare_collection_with_family(db, user, collection_id)
    return ok({"shared": False})
