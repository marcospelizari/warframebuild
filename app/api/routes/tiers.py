"""GET /api/tiers/{category}: a weapon class's tier list from the current release's
Recommended builds (PLAN G92). Made once per release on the runner (it reads every gun's
builds), then kept; only that fill counts against the per-address rate limit."""

from fastapi import APIRouter, Request, Response

from app.api import jobs
from app.api.errors import ApiFailure
from app.api.schemas.base import ApiError
from app.api.schemas.tiers import TierList
from app.api.serving import LISTS_KEPT, remember, served
from app.gamedata.models import Category

ERRORS: dict[int | str, dict[str, object]] = {429: {"model": ApiError}, 503: {"model": ApiError}}

router = APIRouter()


@router.get("/api/tiers/{category}", response_model=TierList, responses=ERRORS)
async def tiers(category: Category, request: Request) -> Response:
    now = served(request)  # one release for the whole request (U11)
    release = now.release
    if release is None:
        raise ApiFailure(503, "no_release", "no builds yet: run `uv run wfb build-all`")
    if release.dataset_hash != now.data.meta.dataset_hash:
        raise ApiFailure(503, "release_mismatch", "the release was built from other game data")
    key = f"tiers:{category}"
    body = now.lists_cache.pop(key, None)
    if body is None:
        request.app.state.rate_limit.check(request)
        body = await jobs.run(now.runner, jobs.tiers, release, category)
    remember(now.lists_cache, key, body, LISTS_KEPT)
    return Response(body, media_type="application/json")
