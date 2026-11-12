import asyncio
import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import serving
from app.api.app import create_app
from app.api.runner import Restarted
from app.gamedata.release import POINTER, current
from app.gamedata.store import GameData


def _copy(releases: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "releases"
    shutil.copytree(releases, copy)
    return copy


def _new_release(releases: Path, new_id: str, source: Path) -> Path:
    """A copy of `source` under its own id, and `current` pointing at it."""
    folder = releases / new_id
    shutil.copytree(source, folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["id"] = new_id
    (folder / "manifest.json").write_text(json.dumps(manifest))
    (releases / POINTER).write_text(new_id + "\n")
    return folder


def _swap(app: FastAPI) -> bool:
    """What the watcher does each round, on this thread."""
    new = serving.load_next(app)
    if new is not None:
        serving.install(app, new)
    return new is not None


def _app(tmp_path: Path, gamedata: GameData, releases: Path) -> FastAPI:
    return create_app(web_dist=tmp_path / "missing", data=gamedata, releases=releases)


def test_a_new_release_is_served_without_a_restart(
    tmp_path: Path, gamedata: GameData, releases: Path
) -> None:
    copy = _copy(releases, tmp_path)
    original = current(copy)
    assert original is not None
    app = _app(tmp_path, gamedata, copy)
    client = TestClient(app)
    assert client.get("/api/weapons/soma-prime/builds").status_code == 200
    old = app.state.served
    assert not _swap(app)  # nothing new

    _new_release(copy, "f" * 16, original)
    assert _swap(app)
    assert app.state.served.release.id == "f" * 16
    response = client.get("/api/weapons/soma-prime/builds")
    assert (response.status_code, response.json()["release"]) == (200, "f" * 16)
    assert response.headers["etag"].startswith(f'"{"f" * 16}-')
    assert app.state.served.builds_cache.keys() == {"soma-prime"}  # old cache left behind
    assert not _swap(app)

    async def on_old_runner() -> None:
        await old.runner.run(lambda: None)

    with pytest.raises(Restarted):  # the old pool takes no new job
        asyncio.run(on_old_runner())


def test_a_release_that_fails_to_load_keeps_the_old_one(
    tmp_path: Path, gamedata: GameData, releases: Path, caplog: pytest.LogCaptureFixture
) -> None:
    copy = _copy(releases, tmp_path)
    original = current(copy)
    assert original is not None
    app = _app(tmp_path, gamedata, copy)
    old = app.state.served
    broken = _new_release(copy, "e" * 16, original)
    (broken / "gamedata/meta.json").write_text('{"schema_version": 0}')
    assert not _swap(app)
    assert app.state.served is old
    assert not _swap(app)  # not retried until `current` changes
    assert len([r for r in caplog.records if "not served" in r.message]) == 1

    _new_release(copy, "d" * 16, original)
    assert _swap(app)
    assert app.state.served.release.id == "d" * 16


def test_the_running_app_picks_up_a_new_release(
    tmp_path: Path, gamedata: GameData, releases: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(serving, "INTERVAL_S", 0.05)
    copy = _copy(releases, tmp_path)
    original = current(copy)
    assert original is not None
    with TestClient(_app(tmp_path, gamedata, copy)) as client:
        _new_release(copy, "c" * 16, original)
        deadline = time.monotonic() + 10
        while client.get("/api/weapons/soma-prime/builds").json()["release"] != "c" * 16:
            assert time.monotonic() < deadline, "new release never served"
            time.sleep(0.05)
