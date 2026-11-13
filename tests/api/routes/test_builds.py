import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import SERVED_CODE, create_app
from app.api.rate_limit import RateLimit
from app.gamedata.release import current
from app.gamedata.store import GameData
from app.optimize.search import rounded
from tests.test_layers import ALLOWED


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData, releases: Path) -> TestClient:
    app = create_app(web_dist=tmp_path / "missing", data=gamedata, releases=releases)
    app.state.rate_limit = RateLimit(rate=1e9, burst=10**9)
    return TestClient(app)


def test_plain_gun_builds_are_scored_like_calc(client: TestClient) -> None:
    response = client.get("/api/weapons/soma-prime/builds")
    assert response.status_code == 200
    body = response.json()
    assert response.headers["etag"].startswith(f'"{body["release"]}-')
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


def test_builds_list_what_was_not_calculated(client: TestClient) -> None:
    """U5: entries the search left out, each with the text it could not calculate."""
    rows = client.get("/api/weapons/soma-prime/builds").json()["not_modelled"]
    assert rows
    assert {r["support"] for r in rows} <= {"partial", "unsupported"}
    assert all(r["text"] for r in rows)
    assert "Serration" not in {r["name"] for r in rows}


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


def test_api_code_change_changes_the_etag(client: TestClient) -> None:
    """Review P2: the response is made by API code too; new code must not answer 304."""
    etag = client.get("/api/weapons/soma-prime/builds").headers["etag"]
    client.app.state.api_version = "other"  # type: ignore[attr-defined]
    again = client.get("/api/weapons/soma-prime/builds", headers={"If-None-Match": etag})
    assert again.status_code == 200 and again.headers["etag"] != etag


def test_etag_hashes_every_layer_the_api_runs() -> None:
    """Review P3: a change in optimizer code (e.g. `unmodelled`) must change the ETag too."""
    assert set(SERVED_CODE) == {"api", *ALLOWED["api"]}


def test_no_release_yet_answers_503(tmp_path: Path, gamedata: GameData) -> None:
    client = TestClient(create_app(web_dist=tmp_path, data=gamedata, releases=tmp_path))
    response = client.get("/api/weapons/soma-prime/builds")
    assert (response.status_code, response.json()["code"]) == (503, "no_release")


def test_release_of_other_data_answers_503(client: TestClient) -> None:
    app = client.app
    now = app.state.served  # type: ignore[attr-defined]
    app.state.served = replace(now, release=replace(now.release, dataset_hash="0" * 16))  # type: ignore[attr-defined]
    response = client.get("/api/weapons/soma-prime/builds")
    assert (response.status_code, response.json()["code"]) == (503, "release_mismatch")


def test_app_loads_its_data_from_the_current_release(tmp_path: Path, releases: Path) -> None:
    """C4: /calc and /builds read the same release."""
    with TestClient(create_app(web_dist=tmp_path, releases=releases)) as client:
        state = client.app.state  # type: ignore[attr-defined]
        assert state.served.data.meta.dataset_hash == state.served.release.dataset_hash
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


def test_every_variant_carries_its_primer_build(client: TestClient, releases: Path) -> None:
    """G49: the Primer build with its numbers and how they were counted."""
    for slug in ("soma-prime", "kuva-hind"):
        body = client.get(f"/api/weapons/{slug}/builds").json()
        for variant in body["variants"]:
            primer = variant["primer"]
            assert primer["boost"] >= 1 and primer["enemies"] >= 1
            assert primer["build"]["status"] in ("optimal", "best_found")
            assert primer["assumptions"]
    folder = current(releases)
    assert folder is not None and (folder / "primers.json").is_file()
    good = set(json.loads((folder / "primers.json").read_text())["good"])
    body = client.get("/api/weapons/soma-prime/builds").json()
    assert body["good_primer"] == ("soma-prime" in good)
    items = {w["slug"]: w for w in client.get("/api/weapons").json()["weapons"]}
    assert all(items[s]["good_primer"] == (s in good) for s in ("soma-prime", "kuva-hind"))
