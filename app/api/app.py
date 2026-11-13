"""FastAPI application: JSON API under /api, built frontend (web/dist) for everything else."""

import asyncio
import hashlib
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.types import Scope

from app.api import errors, headers, pages, serving
from app.api.rate_limit import RateLimit
from app.api.routes import builds, calc, img, mods, sitemap, updates, weapons
from app.gamedata.release import Release, open_current
from app.gamedata.store import GameData, load

ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = ROOT / "web" / "dist"
GAMEDATA = ROOT / "gamedata"
RELEASES = ROOT / "cache" / "releases"
IMG = ROOT / "cache" / "img"
ART = ROOT / "cache" / "raw" / "wiki" / "img"  # card art saved by hand (T2), never committed
# CPU work (E6/E7): runner size = concurrency cap; one uvicorn worker keeps it global.
WORKERS = max(1, min(4, (os.cpu_count() or 2) // 2))
QUEUE = 2 * WORKERS  # jobs waiting for a permit; more is 503
TIMEOUT_S = 5.0  # a request stops waiting; a job at 2x restarts the pool

log = logging.getLogger(__name__)


NOT_PAGES = frozenset({"api", "img", "assets"})


class Health(BaseModel):
    status: str
    version: str


class SpaFiles(StaticFiles):
    """Unknown page paths get index.html, so client routes survive a reload (F1); a missing
    file under /api, /img or /assets stays a 404 (an old asset must never cache as HTML)."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or path.split("/", 1)[0] in NOT_PAGES:
                raise
            return await super().get_response("index.html", scope)


def create_app(
    web_dist: Path = WEB_DIST,
    data: GameData | None = None,
    releases: Path = RELEASES,
    img_dir: Path = IMG,
    art_dir: Path = ART,
    public_origin: str | None = None,
) -> FastAPI:
    """Data and builds come from the current release (C4); before the first
    `wfb build-all`, or when the release no longer loads (e.g. an older schema), data from
    gamedata/ and /builds answers 503. A new release is picked up while running (U11)."""
    try:
        release = open_current(releases)
    except (OSError, ValueError, KeyError) as error:
        log.warning("current release unreadable (%s): serving gamedata/ without builds", error)
        release = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.served is None:
            app.state.served = _first(app, release)
        watcher = asyncio.create_task(serving.watch(app))
        try:
            yield
        finally:
            watcher.cancel()
            app.state.served.runner.shutdown()

    app = FastAPI(
        title="warframeBuild",
        version=version("warframebuild"),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.releases = releases
    app.state.api_version = api_version()
    app.state.failed_release = None
    app.state.img_dir = img_dir
    app.state.art_dir = art_dir
    app.state.web_dist = web_dist
    app.state.public_origin = pages.origin(public_origin) if public_origin else None
    app.state.rate_limit = RateLimit()
    # Injected data (tests) cannot reach a spawned process: threads share it instead.
    app.state.pool = serving.Pool(WORKERS, QUEUE, TIMEOUT_S, processes=data is None)
    app.state.served = (
        serving.Served(data, release, app.state.pool.runner(data, GAMEDATA)) if data else None
    )
    errors.install(app)
    headers.install(app, https=(app.state.public_origin or "").startswith("https://"))
    app.include_router(calc.router)
    app.include_router(builds.router)
    app.include_router(weapons.router)
    app.include_router(mods.router)
    app.include_router(img.router)
    app.include_router(updates.router)
    app.include_router(sitemap.router)

    @app.get("/api/health")
    def health() -> Health:
        return Health(status="ok", version=version("warframebuild"))

    if web_dist.is_dir():
        app.include_router(pages.router)  # before the mount: weapon URLs get their meta tags
        app.mount("/", SpaFiles(directory=web_dist, html=True), name="web")
    else:

        @app.get("/", include_in_schema=False)
        def not_built() -> PlainTextResponse:
            return PlainTextResponse(
                "Frontend not built: run `npm run build` in web/.", status_code=503
            )

    return app


SERVED_CODE = ("api", "domain", "gamedata", "optimize")  # the API and the layers it imports


def api_version() -> str:
    """Hash of the code that shapes a response: part of the /builds ETag."""
    digest = hashlib.sha256()
    root = Path(__file__).parent.parent
    for path in sorted(p for layer in SERVED_CODE for p in (root / layer).rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()[:12]


def _first(app: FastAPI, release: Release | None) -> serving.Served:
    """At startup: the release's data, or gamedata/ without builds when it does not load."""
    data, folder = None, GAMEDATA
    if release is not None:
        try:
            data, folder = load(release.gamedata), release.gamedata
        except (OSError, ValueError) as error:
            log.warning("release unusable (%s): serving gamedata/ without builds", error)
            app.state.failed_release = release.id  # the watcher waits for the next one
            release = None
    if data is None:
        data = load(GAMEDATA)
    # Workers load the same folder the app serves (C4).
    pool: serving.Pool = app.state.pool
    return serving.Served(data, release, pool.runner(data, folder))
