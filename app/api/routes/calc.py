"""POST /api/calc: evaluate one build (no search): hit DPS and the combat score. Runs on
the app's runner (E6/E7), rate-limited per address."""

from fastapi import APIRouter, Request, Response

from app.api import jobs
from app.api.schemas.base import ApiError
from app.api.schemas.build import Build, CalcRequest
from app.api.serving import served

ERRORS: dict[int | str, dict[str, object]] = {
    404: {"model": ApiError},
    413: {"model": ApiError},
    422: {"model": ApiError},
    429: {"model": ApiError},
    503: {"model": ApiError},
}

router = APIRouter()


@router.post("/api/calc", response_model=Build, responses=ERRORS)
async def calc(body: CalcRequest, request: Request) -> Response:
    request.app.state.rate_limit.check(request)
    built = await jobs.run(
        served(request).runner,
        jobs.calc,
        body.model_dump_json(),
        current=lambda: served(request).runner,  # /calc reads no release: safe on a newer one
    )
    return Response(built, media_type="application/json")
