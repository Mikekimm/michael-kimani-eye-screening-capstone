"""Application errors raised by services and translated to HTTP responses in one place.

Services never import FastAPI; they raise these domain errors and ``register_error_handlers``
maps each one to a status code with a plain-language message.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthenticationError(AppError):
    status_code = 401
    code = "not_authenticated"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnprocessableImageError(AppError):
    """The upload is not a usable fundus image (wrong type, too large, undecodable, poor quality)."""
    status_code = 422
    code = "unusable_image"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message, "details": exc.details},
            headers=headers,
        )
