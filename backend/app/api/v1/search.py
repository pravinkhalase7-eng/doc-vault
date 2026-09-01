from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.common import SearchQuery
from app.search.hybrid import hybrid_search
from app.documents.service import list_documents, serialize_document

router = APIRouter(prefix="/search", tags=["search"])


@router.post("")
async def search(payload: SearchQuery, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows, total = await list_documents(
        db,
        user.id,
        q=payload.q,
        category_id=payload.category_id,
        limit=payload.limit,
        offset=payload.offset,
    )
    semantic = await hybrid_search(db, user.id, payload.q or "", limit=payload.limit) if payload.q else []
    return {
        "success": True,
        "data": {
            "items": [serialize_document(d) for d in rows],
            "semantic": semantic,
            "total": total,
        },
    }
