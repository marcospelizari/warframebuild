from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.gamedata.store import GameData


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData) -> TestClient:
    return TestClient(create_app(web_dist=tmp_path, data=gamedata, releases=tmp_path))


def test_picker_lists_category_mods_with_fit_and_reason(client: TestClient) -> None:
    body = client.get("/api/mods", params={"weapon": "soma-prime"}).json()
    by_name = {m["name"]: m for m in body["mods"]}
    assert by_name["Serration"]["compatible"] is True
    assert by_name["Serration"]["reason"] is None
    assert by_name["Serration"]["family"] is not None
    assert "Hornet Strike" not in by_name  # pistol mods are not offered on rifles
    blunderbuss = by_name["Blunderbuss"]  # shotgun mod: same category, other class (G82)
    assert (blunderbuss["compatible"], blunderbuss["reason"]) == (False, "does not fit Soma Prime")
    unfit = [m for m in body["mods"] if not m["compatible"]]
    assert unfit and all(m["reason"] == "does not fit Soma Prime" for m in unfit)
    assert body["perks"]  # Soma Prime is an Incarnon gun


def test_gun_without_incarnon_has_no_perk_tiers(client: TestClient, gamedata: GameData) -> None:
    plain = next(w for w in gamedata.weapons if w.unique_name not in gamedata.incarnon_by_id)
    assert client.get("/api/mods", params={"weapon": plain.slug}).json()["perks"] == []


def test_incarnon_gun_lists_its_perk_tiers(client: TestClient, gamedata: GameData) -> None:
    body = client.get("/api/mods", params={"weapon": "lex-prime"}).json()
    lex = next(w for w in gamedata.weapons if w.slug == "lex-prime")
    perks = gamedata.incarnon_by_id[lex.unique_name].perks
    assert [t["tier"] for t in body["perks"]] == sorted({p.tier for p in perks})
    assert sum(len(t["options"]) for t in body["perks"]) == len(perks)
    assert all(a["unique_name"] for a in body["arcanes"])


def test_unknown_gun_is_404(client: TestClient) -> None:
    response = client.get("/api/mods", params={"weapon": "nope"})
    assert (response.status_code, response.json()["field"]) == (404, "weapon")


def test_arcane_reason_names_the_arcane_type(client: TestClient, gamedata: GameData) -> None:
    body = client.get("/api/mods", params={"weapon": "soma-prime"}).json()
    unfit = [a for a in body["arcanes"] if not a["compatible"]]
    types = {a.unique_name: a.weapon_type for a in gamedata.arcanes}
    assert unfit and all(a["reason"] == f"{types[a['unique_name']]} only" for a in unfit)
