"""Error responses: always `{code, message, field}` (G18); a crash answers a generic 500
with no detail (S7); Starlette re-raises it, so the server logs the stack trace."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.headers import SECURITY
from app.api.schemas.base import ApiError

MAX_BODY = 4096  # bytes; /calc requests are a few hundred


class ApiFailure(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        field: str | None = None,
        retry_after: int | None = None,  # seconds, sent as Retry-After (429/503)
    ) -> None:
        super().__init__(message)
        self.status, self.error = status, ApiError(code=code, message=message, field=field)
        self.headers = {"Retry-After": str(retry_after)} if retry_after is not None else None


def response(status: int, code: str, message: str, field: str | None = None) -> JSONResponse:
    error = ApiError(code=code, message=message, field=field)
    return JSONResponse(error.model_dump(), status_code=status)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiFailure)
    async def failure(_: Request, exc: ApiFailure) -> JSONResponse:
        return JSONResponse(exc.error.model_dump(), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        named = [str(p) for p in first["loc"][1:] if first["type"] != "json_invalid"]
        field = ".".join(named) or None
        return response(422, "invalid_request", str(first["msg"]), field)

    @app.exception_handler(Exception)
    async def crash(_: Request, __: Exception) -> JSONResponse:
        # Answered outside every other middleware, so it carries the headers itself.
        failed = response(500, "internal_error", "Something went wrong on our side.")
        failed.headers.update(SECURITY)
        return failed

    @app.middleware("http")
    async def body_limit(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method in ("POST", "PUT", "PATCH"):
            length = request.headers.get("content-length")
            if length is None or not length.isdigit():
                return response(411, "length_required", "Content-Length required")
            if int(length) > MAX_BODY:
                return response(413, "body_too_large", f"body over {MAX_BODY} bytes")
        return await call_next(request)
