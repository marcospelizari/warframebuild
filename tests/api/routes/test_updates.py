import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.gamedata.release import current
from app.gamedata.store import GameData
from app.gamedata.updates import UPDATES, Update, Updates
from app.pipeline.publish import dump


def _client(tmp_path: Path, gamedata: GameData, releases: Path) -> TestClient:
    return TestClient(create_app(web_dist=tmp_path / "missing", data=gamedata, releases=releases))


def test_data_info_names_the_game_data(tmp_path: Path, gamedata: GameData, releases: Path) -> None:
    body = _client(tmp_path, gamedata, releases).get("/api/data").json()
    assert body == {"game_update": gamedata.meta.game_update, "checked": gamedata.meta.fetched}


def test_updates_come_from_the_current_release(
    tmp_path: Path, gamedata: GameData, releases: Path
) -> None:
    copy = tmp_path / "releases"
    shutil.copytree(releases, copy)
    folder = current(copy)
    assert folder is not None
    update = Update(
        kind="calculator",
        release="r2",
        date="2026-11-13",
        game_update="Update 44.0",
        summary=["Builds changed by our calculation, not by the game."],
        entries=[],
        guns=[],
        unavailable=[],
    )
    (folder / UPDATES).write_bytes(dump(Updates(updates=[update])))
    body = _client(tmp_path, gamedata, copy).get("/api/updates").json()
    assert body["data"]["checked"] == gamedata.meta.fetched
    assert [u["summary"] for u in body["updates"]] == [update.summary]


def test_no_release_means_no_updates(tmp_path: Path, gamedata: GameData) -> None:
    body = _client(tmp_path, gamedata, tmp_path / "none").get("/api/updates").json()
    assert body["updates"] == []
