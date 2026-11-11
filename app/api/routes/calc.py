"""POST /api/calc: evaluate one build (no search): hit DPS and the combat score."""

from fastapi import APIRouter, Request

from app.api.build_response import build_response
from app.api.schemas import ApiError, Build, CalcRequest

ERRORS: dict[int | str, dict[str, object]] = {
    404: {"model": ApiError},
    413: {"model": ApiError},
    422: {"model": ApiError},
}

router = APIRouter()


@router.post("/api/calc", responses=ERRORS)
def calc(body: CalcRequest, request: Request) -> Build:
    return build_response(request.app.state.data, body)
