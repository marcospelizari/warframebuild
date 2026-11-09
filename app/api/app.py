"""FastAPI application: JSON API under /api, built frontend (web/dist) for everything else."""

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

from app.api import errors
from app.api.routes import calc
from app.gamedata.store import GameData, load

ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = ROOT / "web" / "dist"
GAMEDATA = ROOT / "gamedata"


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


def create_app(web_dist: Path = WEB_DIST, data: GameData | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if getattr(app.state, "data", None) is None:
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
    errors.install(app)
    app.include_router(calc.router)

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
