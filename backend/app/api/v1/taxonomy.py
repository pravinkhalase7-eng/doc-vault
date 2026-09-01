from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import get_current_user
from app.database import get_db
from app.models.document import Category, DocumentType, Tag
from app.models.user import User
from app.schemas.common import CategoryCreate

router = APIRouter(tags=["taxonomy"])


def ok(data):
    return {"success": True, "data": data}


@router.get("/categories")
async def categories(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(Category).where(
                Category.deleted_at.is_(None),
                (Category.user_id == user.id) | (Category.is_system.is_(True)),
            ).order_by(Category.sort_order)
        )
    ).all()
    return ok([{"id": c.id, "name": c.name, "slug": c.slug, "is_system": c.is_system} for c in rows])


@router.post("/categories")
async def create_category(
    payload: CategoryCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    from app.documents.service import _slug

    cat = Category(user_id=user.id, name=payload.name, slug=_slug(payload.name), is_system=False)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return ok({"id": cat.id, "name": cat.name, "slug": cat.slug, "is_system": False})


@router.get("/document-types")
async def document_types(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(DocumentType).where(
                DocumentType.deleted_at.is_(None),
                (DocumentType.user_id == user.id) | (DocumentType.is_system.is_(True)),
            )
        )
    ).all()
    return ok(
        [
            {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "category_id": t.category_id,
                "default_sensitivity": t.default_sensitivity.value,
            }
            for t in rows
        ]
    )


@router.get("/tags")
async def tags(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Tag).where(Tag.user_id == user.id))).all()
    return ok([{"id": t.id, "name": t.name, "slug": t.slug} for t in rows])
