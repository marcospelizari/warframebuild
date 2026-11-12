"""GET /api/weapons/{slug}/builds: a gun's precomputed builds from the current release, each
scored by the /calc code (PLAN Q28b, option A); never a search. ETag = release id. A gun
not in the in-memory cache is filled in on the runner (E6/E7); only those fills count
against the per-address rate limit."""

from fastapi import APIRouter, Request, Response

from app.api import jobs
from app.api.errors import ApiFailure
from app.api.schemas.base import ApiError
from app.api.schemas.stored import BuildsResponse
from app.api.serving import served
from app.gamedata.release import Release
from app.gamedata.store import GameData

CACHED_GUNS = 64  # filled-in responses kept in memory

ERRORS: dict[int | str, dict[str, object]] = {
    404: {"model": ApiError},
    429: {"model": ApiError},
    503: {"model": ApiError},
}

router = APIRouter()


@router.get("/api/weapons/{slug}/builds", response_model=BuildsResponse, responses=ERRORS)
async def builds(slug: str, request: Request) -> Response:
    now = served(request)  # one release for the whole request (U11)
    data: GameData = now.data
    release: Release | None = now.release
    if release is None:
        raise ApiFailure(503, "no_release", "no builds yet: run `uv run wfb build-all`")
    if release.dataset_hash != data.meta.dataset_hash:
        raise ApiFailure(503, "release_mismatch", "the release was built from other game data")
    if slug not in data.weapon_by_slug:  # also keeps `slug` from naming any other file
        raise ApiFailure(404, "unknown_weapon", "no such weapon", "slug")
    headers = {"ETag": f'"{release.id}"', "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    cache = now.builds_cache
    body = cache.pop(slug, None)
    if body is None:
        request.app.state.rate_limit.check(request)
        body = await jobs.run(now.runner, jobs.builds, release, slug)
    cache[slug] = body  # most recent last
    while len(cache) > CACHED_GUNS:
        cache.pop(next(iter(cache)))
    return Response(body, media_type="application/json", headers=headers)
