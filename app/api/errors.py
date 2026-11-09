"""Error responses: always `{code, message, field}` (G18)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.schemas import ApiError

MAX_BODY = 4096  # bytes; /calc requests are a few hundred


class ApiFailure(Exception):
    def __init__(self, status: int, code: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.status, self.error = status, ApiError(code=code, message=message, field=field)


def response(status: int, code: str, message: str, field: str | None = None) -> JSONResponse:
    error = ApiError(code=code, message=message, field=field)
    return JSONResponse(error.model_dump(), status_code=status)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiFailure)
    async def failure(_: Request, exc: ApiFailure) -> JSONResponse:
        return JSONResponse(exc.error.model_dump(), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        named = [str(p) for p in first["loc"][1:] if first["type"] != "json_invalid"]
        field = ".".join(named) or None
        return response(422, "invalid_request", str(first["msg"]), field)

    @app.middleware("http")
    async def body_limit(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method in ("POST", "PUT", "PATCH"):
            length = request.headers.get("content-length")
            if length is None or not length.isdigit():
                return response(411, "length_required", "Content-Length required")
            if int(length) > MAX_BODY:
                return response(413, "body_too_large", f"body over {MAX_BODY} bytes")
        return await call_next(request)
