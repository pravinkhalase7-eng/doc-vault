from fastapi import APIRouter

from app.api.v1 import admin, ai, auth, documents, family, ingest, privacy, push, search, sharing, taxonomy, users, workspace
from app.api.v1.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(documents.router)
api_router.include_router(ingest.router)
api_router.include_router(taxonomy.router)
api_router.include_router(search.router)
api_router.include_router(ai.router)
api_router.include_router(workspace.router)
api_router.include_router(sharing.router)
api_router.include_router(family.router)
api_router.include_router(privacy.router)
api_router.include_router(push.router)
api_router.include_router(admin.router)
