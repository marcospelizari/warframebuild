from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.gamedata.store import GameData

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData) -> TestClient:
    (tmp_path / "img/weapons").mkdir(parents=True)
    (tmp_path / "img/weapons/soma-prime.png").write_bytes(PNG)
    app = create_app(web_dist=tmp_path, data=gamedata, releases=tmp_path, img_dir=tmp_path / "img")
    return TestClient(app)


def test_lists_every_gun_with_its_flags(client: TestClient, gamedata: GameData) -> None:
    body = client.get("/api/weapons").json()
    assert len(body["weapons"]) == len(gamedata.weapons)
    by_slug = {w["slug"]: w for w in body["weapons"]}
    assert by_slug["soma-prime"]["image"] == "/img/weapons/soma-prime.png"
    assert by_slug["lex-prime"]["image"] is None  # not cached
    assert by_slug["lex-prime"]["incarnon"] is True
    assert by_slug["kuva-hind"]["progenitor"] is True
    assert {e["name"] for e in body["excluded"]} == {e.name for e in gamedata.meta.excluded_weapons}


def test_filters_by_category_and_plain_name_search(client: TestClient) -> None:
    body = client.get("/api/weapons", params={"category": "secondary", "q": "LEX"}).json()
    assert {w["slug"] for w in body["weapons"]} >= {"lex-prime"}
    assert all(w["category"] == "secondary" and "lex" in w["name"].lower() for w in body["weapons"])
    regex = client.get("/api/weapons", params={"q": ".*"}).json()  # no regex from input
    assert regex["weapons"] == []


def test_search_text_is_capped(client: TestClient) -> None:
    response = client.get("/api/weapons", params={"q": "x" * 65})
    assert (response.status_code, response.json()["code"]) == (422, "invalid_request")
