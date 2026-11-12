"""GET /api/data (the game data a page shows, U4) and GET /api/updates (U10)."""

from fastapi import APIRouter, Request

from app.api.schemas.updates import DataInfo, UpdatesResponse
from app.api.serving import served
from app.gamedata.release import Release
from app.gamedata.store import GameData

router = APIRouter()


def _info(data: GameData) -> DataInfo:
    return DataInfo(game_update=data.meta.game_update, checked=data.meta.fetched)


@router.get("/api/data")
def data_info(request: Request) -> DataInfo:
    return _info(served(request).data)


@router.get("/api/updates")
def updates(request: Request) -> UpdatesResponse:
    now = served(request)
    data: GameData = now.data
    release: Release | None = now.release
    found = release.updates.updates if release else []
    return UpdatesResponse(data=_info(data), updates=found)
