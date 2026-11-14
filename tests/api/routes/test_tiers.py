from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.rate_limit import RateLimit
from app.gamedata.store import GameData
from tests.api.conftest import GUNS


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData, releases: Path) -> TestClient:
    """The app on the test release; its data holds only the release's guns, as a real
    release holds every gun of its data."""
    data = replace(gamedata, weapons=[w for w in gamedata.weapons if w.name in GUNS])
    app = create_app(web_dist=tmp_path / "missing", data=data, releases=releases)
    app.state.rate_limit = RateLimit(rate=1e9, burst=10**9)
    return TestClient(app)


def test_primary_tier_list_ranks_every_gun_from_its_recommended_build(client: TestClient) -> None:
    body = client.get("/api/tiers/primary").json()
    assert [t["name"] for t in body["tiers"]] == ["S", "A", "B", "C", "D", "E", "F"]
    assert body["tiers"][-1]["up_to"] is None
    assert (body["level"], body["factions"]) == (120, 8)  # from the enemy data
    guns = [g for t in body["tiers"] for g in t["guns"]]
    assert sorted(g["slug"] for g in guns) == ["kuva-hind", "soma-prime"]
    assert body["tiers"][0]["guns"][0]["kill_time"] == body["fastest"]  # the best is S
    times = [g["kill_time"] for g in guns]
    assert times == sorted(times)  # fastest first, tier by tier
    recommended = client.get("/api/weapons/soma-prime/builds").json()["variants"][0]["recommended"]
    soma = next(g for g in guns if g["slug"] == "soma-prime")
    assert soma["kill_time"] == pytest.approx(1 / recommended["score"])


def test_class_without_guns_has_empty_tiers(client: TestClient) -> None:
    body = client.get("/api/tiers/secondary").json()
    assert all(t["guns"] == [] for t in body["tiers"])


def test_unknown_class_is_rejected(client: TestClient) -> None:
    assert client.get("/api/tiers/melee").status_code == 422


def test_no_release_yet_answers_503(tmp_path: Path, gamedata: GameData) -> None:
    client = TestClient(create_app(web_dist=tmp_path, data=gamedata, releases=tmp_path))
    response = client.get("/api/tiers/primary")
    assert (response.status_code, response.json()["code"]) == (503, "no_release")
