from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.api.v1 import api_router
from app.config import get_settings
from app.documents.service import seed_taxonomy
from app.exceptions import (
    AppError,
    app_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.logging import configure_logging, new_request_id
from app.security.rate_limit import rate_limit_middleware

settings = get_settings()
configure_logging(settings.debug and not settings.is_production)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = new_request_id()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
        return response


def create_app() -> FastAPI:
    application = FastAPI(
        title="DocVault AI",
        version="1.0.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )
    application.add_middleware(RequestIDMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    rate_limit_middleware(application)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(HTTPException, http_error_handler)
    application.add_exception_handler(Exception, unhandled_error_handler)
    application.include_router(api_router, prefix="/api/v1")

    @application.on_event("startup")
    async def startup() -> None:
        from app.database import SessionLocal

        async with SessionLocal() as db:
            try:
                await seed_taxonomy(db)
            except Exception:
                pass
            try:
                from app.auth.service import seed_guest_user

                await seed_guest_user(db)
            except Exception:
                pass

    return application


app = create_app()
