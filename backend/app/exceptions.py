"""Typed application errors mapped to consistent API payloads."""

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.logging import get_logger

log = get_logger("errors")


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, code: str = "NOT_FOUND", message: str = "Resource not found") -> None:
        super().__init__(code, message, 404)


class ForbiddenError(AppError):
    def __init__(self, code: str = "FORBIDDEN", message: str = "Not allowed") -> None:
        super().__init__(code, message, 403)


class UnauthorizedError(AppError):
    def __init__(self, code: str = "UNAUTHORIZED", message: str = "Authentication required") -> None:
        super().__init__(code, message, 401)


class ConflictError(AppError):
    def __init__(self, code: str = "CONFLICT", message: str = "Conflict") -> None:
        super().__init__(code, message, 409)


class RateLimitError(AppError):
    def __init__(self, code: str = "RATE_LIMITED", message: str = "Too many requests") -> None:
        super().__init__(code, message, 429)


class PrivacyRejectedError(AppError):
    def __init__(
        self,
        message: str = "This request was blocked by the privacy gateway.",
        details: dict | None = None,
    ) -> None:
        super().__init__("PRIVACY_REJECTED", message, 403, details)


def error_payload(code: str, message: str, details: dict | None = None) -> dict:
    error: dict = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"success": False, "error": error}


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    code = "HTTP_ERROR"
    if exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 429:
        code = "RATE_LIMITED"
    return JSONResponse(status_code=exc.status_code, content=error_payload(code, message))


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else None
    if not first:
        message = "Invalid request"
    else:
        loc = ".".join(str(part) for part in first.get("loc", []) if part != "body")
        detail = first.get("msg", "Invalid request")
        message = f"{loc}: {detail}" if loc else str(detail)
    return JSONResponse(
        status_code=422,
        content=error_payload("VALIDATION_ERROR", message, {"errors": errors}),
    )


async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", error=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content=error_payload("INTERNAL_ERROR", "An unexpected error occurred"),
    )
