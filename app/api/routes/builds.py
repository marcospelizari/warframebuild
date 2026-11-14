"""GET /api/weapons/{slug}/builds: a gun's precomputed builds from the current release, each
scored by the /calc code (PLAN Q28b, option A); never a search. ETag = release id + API
code version. A gun not in the in-memory cache is filled in on the runner (E6/E7); only
those fills count against the per-address rate limit."""

import asyncio

from fastapi import APIRouter, Request, Response

from app.api import jobs
from app.api.errors import ApiFailure
from app.api.schemas.base import ApiError
from app.api.schemas.stored import BuildsResponse
from app.api.serving import Served, remember, served
from app.gamedata.release import Release
from app.gamedata.store import GameData

CACHED_GUNS = 64  # filled-in responses kept in memory
# A fill is slow on the heaviest guns (~4 s on a fast desktop): a request waits the
# runner's usual time, the fill itself runs up to FILL_TIMEOUT_S and its answer is kept,
# so a retry finds it ready or joins it.
FILL_TIMEOUT_S = 30.0

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
    # The response is made by API code too: a code change must not answer 304.
    etag = f'"{release.id}-{request.app.state.api_version}"'
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    body = now.builds_cache.pop(slug, None)
    if body is not None:
        remember(now.builds_cache, slug, body, CACHED_GUNS)
    else:
        fill = now.fills.get(slug)  # a retry joins the fill already running
        if fill is None:
            request.app.state.rate_limit.check(request)
            run = jobs.run(now.runner, jobs.builds, release, slug, timeout=FILL_TIMEOUT_S)
            fill = now.fills[slug] = asyncio.ensure_future(run)
            fill.add_done_callback(lambda done: _filled(now, slug, done))
        try:
            body = await asyncio.wait_for(asyncio.shield(fill), now.runner.timeout)
        except TimeoutError:
            raise ApiFailure(503, "timeout", "the request took too long", retry_after=1) from None
    return Response(body, media_type="application/json", headers=headers)


def _filled(now: Served, slug: str, fill: "asyncio.Task[bytes]") -> None:
    """Keep the answer even when every request waiting for it has gone."""
    now.fills.pop(slug, None)
    if not fill.cancelled() and fill.exception() is None:
        remember(now.builds_cache, slug, fill.result(), CACHED_GUNS)
