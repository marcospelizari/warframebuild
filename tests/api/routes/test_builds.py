import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.rate_limit import RateLimit
from app.gamedata.release import current
from app.gamedata.store import GameData
from app.optimize.search import rounded


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData, releases: Path) -> TestClient:
    app = create_app(web_dist=tmp_path / "missing", data=gamedata, releases=releases)
    app.state.rate_limit = RateLimit(rate=1e9, burst=10**9)
    return TestClient(app)


def test_plain_gun_builds_are_scored_like_calc(client: TestClient) -> None:
    response = client.get("/api/weapons/soma-prime/builds")
    assert response.status_code == 200
    body = response.json()
    assert response.headers["etag"] == f'"{body["release"]}"'
    assert body["weapon"]["name"] == "Soma Prime"
    assert body["elements"] == []
    [variant] = body["variants"]
    assert len(variant["factions"]) == 8
    assert rounded(variant["max"]["build"]["dps"]["max_score"]) == variant["max"]["score"]
    recommended = variant["recommended"]
    assert rounded(1 / recommended["build"]["combat"]["score"]) == recommended["score"]
    for faction, stored in variant["factions"].items():
        scores = {f["faction"]: f["score"] for f in stored["build"]["combat"]["factions"]}
        assert rounded(1 / scores[faction]) == stored["score"]
    enemies = {e["unique_name"] for e in recommended["build"]["combat"]["enemies"]}
    assert set(variant["denominators"]) == enemies


def test_progenitor_gun_has_two_variants_and_element_rows(client: TestClient) -> None:
    body = client.get("/api/weapons/kuva-hind/builds").json()
    first, second = body["variants"]
    assert [r["element"] for r in body["elements"][:2]] == [first["element"], second["element"]]
    assert second["recommended"]["build"]["bonus_element"]["damage_type"] == second["element"]
    assert {b["status"] for b in second["factions"].values()} == {"what_if"}


def test_unchanged_release_answers_304(client: TestClient) -> None:
    etag = client.get("/api/weapons/soma-prime/builds").headers["etag"]
    again = client.get("/api/weapons/soma-prime/builds", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["etag"] == etag


@pytest.mark.parametrize("slug", ["nope", "..%2Fmanifest", "..%2F..%2Fgamedata%2Fmeta"])
def test_unknown_gun_is_404_and_never_names_another_file(client: TestClient, slug: str) -> None:
    response = client.get(f"/api/weapons/{slug}/builds")
    assert response.status_code == 404


def test_no_release_yet_answers_503(tmp_path: Path, gamedata: GameData) -> None:
    client = TestClient(create_app(web_dist=tmp_path, data=gamedata, releases=tmp_path))
    response = client.get("/api/weapons/soma-prime/builds")
    assert (response.status_code, response.json()["code"]) == (503, "no_release")


def test_release_of_other_data_answers_503(client: TestClient) -> None:
    app = client.app
    app.state.release = replace(app.state.release, dataset_hash="0" * 16)  # type: ignore[attr-defined]
    response = client.get("/api/weapons/soma-prime/builds")
    assert (response.status_code, response.json()["code"]) == (503, "release_mismatch")


def test_app_loads_its_data_from_the_current_release(tmp_path: Path, releases: Path) -> None:
    """C4: /calc and /builds read the same release."""
    with TestClient(create_app(web_dist=tmp_path, releases=releases)) as client:
        state = client.app.state  # type: ignore[attr-defined]
        assert state.data.meta.dataset_hash == state.release.dataset_hash
        assert client.get("/api/weapons/soma-prime/builds").status_code == 200


def test_unloadable_release_serves_gamedata_without_builds(tmp_path: Path, releases: Path) -> None:
    """A release from an older schema must not stop the app from starting."""
    broken = tmp_path / "releases"
    shutil.copytree(releases, broken)
    folder = current(broken)
    assert folder is not None
    (folder / "gamedata/meta.json").write_text('{"schema_version": 0}')
    with TestClient(create_app(web_dist=tmp_path, releases=broken)) as client:
        assert client.get("/api/health").status_code == 200
        response = client.get("/api/weapons/soma-prime/builds")
        assert (response.status_code, response.json()["code"]) == (503, "no_release")


def test_pruned_release_answers_503(tmp_path: Path, gamedata: GameData, releases: Path) -> None:
    moved = tmp_path / "releases"
    shutil.copytree(releases, moved)
    client = TestClient(create_app(web_dist=tmp_path, data=gamedata, releases=moved))
    folder = current(moved)
    assert folder is not None
    shutil.rmtree(folder / "builds")  # what pruning does to a running server's release
    response = client.get("/api/weapons/soma-prime/builds")
    assert (response.status_code, response.json()["code"]) == (503, "release_gone")


def test_stored_and_calc_layouts_agree(client: TestClient) -> None:
    """E8: the editor's /calc layout for unchanged mods is the stored one."""
    recommended = client.get("/api/weapons/soma-prime/builds").json()["variants"][0]["recommended"]
    assert recommended["build"]["forma"] == recommended["forma"]
    assert set(recommended["without"]) >= set(
        m["mod"] for m in recommended["build"]["slots"] if m["mod"]
    )
