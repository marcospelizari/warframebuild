"""`GET /api/data` and `GET /api/updates` (G90 U4, U10)."""

from app.api.schemas.base import ApiModel
from app.gamedata.updates import Update


class DataInfo(ApiModel):
    """Which game data the site shows (U4): every page's footer."""

    game_update: str | None  # newest content update named in the data
    checked: str  # ISO date the game files were last downloaded


class UpdatesResponse(ApiModel):
    data: DataInfo
    updates: list[Update]  # newest first; empty before the first compared release
