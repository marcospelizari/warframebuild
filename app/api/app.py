"""FastAPI application: JSON API under /api, built frontend (web/dist) for everything else."""

from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


class Health(BaseModel):
    status: str
    version: str


def create_app(web_dist: Path = WEB_DIST) -> FastAPI:
    app = FastAPI(
        title="warframeBuild",
        version=version("warframebuild"),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/api/health")
    def health() -> Health:
        return Health(status="ok", version=version("warframebuild"))

    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    else:

        @app.get("/", include_in_schema=False)
        def not_built() -> PlainTextResponse:
            return PlainTextResponse(
                "Frontend not built: run `npm run build` in web/.", status_code=503
            )

    return app
