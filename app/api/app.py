"""FastAPI application: JSON API under /api, built frontend (web/dist) for everything else."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.types import Scope

from app.api import errors
from app.api.routes import builds, calc, img, mods, weapons
from app.gamedata.release import open_current
from app.gamedata.store import GameData, load

ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = ROOT / "web" / "dist"
GAMEDATA = ROOT / "gamedata"
RELEASES = ROOT / "cache" / "releases"
IMG = ROOT / "cache" / "img"
CACHED_GUNS = 64  # expanded /builds responses kept in memory

log = logging.getLogger(__name__)


class Health(BaseModel):
    status: str
    version: str


class SpaFiles(StaticFiles):
    """Unknown paths outside /api get index.html, so client routes survive a reload (F1)."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or path == "api" or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


def create_app(
    web_dist: Path = WEB_DIST,
    data: GameData | None = None,
    releases: Path = RELEASES,
    img_dir: Path = IMG,
) -> FastAPI:
    """Data and builds come from the current release (C4); before the first
    `wfb build-all`, or when the release no longer loads (e.g. an older schema), data from
    gamedata/ and /builds answers 503."""
    try:
        release = open_current(releases)
    except (OSError, ValueError, KeyError) as error:
        log.warning("current release unreadable (%s): serving gamedata/ without builds", error)
        release = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if getattr(app.state, "data", None) is None:
            app.state.data = None
            if app.state.release is not None:
                try:
                    app.state.data = load(app.state.release.gamedata)
                except (OSError, ValueError) as error:
                    log.warning("release unusable (%s): serving gamedata/ without builds", error)
                    app.state.release = None
            if app.state.data is None:
                app.state.data = load(GAMEDATA)
        yield

    app = FastAPI(
        title="warframeBuild",
        version=version("warframebuild"),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.data = data
    app.state.release = release
    app.state.img_dir = img_dir
    if release is not None:  # /builds answers 503 without one
        app.state.expanded_builds = lru_cache(maxsize=CACHED_GUNS)(
            lambda slug: builds.expand(app.state.data, release, slug)
        )
    errors.install(app)
    app.include_router(calc.router)
    app.include_router(builds.router)
    app.include_router(weapons.router)
    app.include_router(mods.router)
    app.include_router(img.router)

    @app.get("/api/health")
    def health() -> Health:
        return Health(status="ok", version=version("warframebuild"))

    if web_dist.is_dir():
        app.mount("/", SpaFiles(directory=web_dist, html=True), name="web")
    else:

        @app.get("/", include_in_schema=False)
        def not_built() -> PlainTextResponse:
            return PlainTextResponse(
                "Frontend not built: run `npm run build` in web/.", status_code=503
            )

    return app
