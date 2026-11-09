from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.gamedata.store import GameData


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData) -> TestClient:
    return TestClient(create_app(web_dist=tmp_path / "missing", data=gamedata))


def _id(data: GameData, name: str) -> str:
    return next(m.unique_name for m in data.mods.mods if m.name == name)


def test_valid_build(client: TestClient, gamedata: GameData) -> None:
    body = {"weapon": "kuva-hind", "mods": [_id(gamedata, "Serration")], "bonus_element": "heat"}
    response = client.post("/api/calc", json=body)
    assert response.status_code == 200
    build = response.json()
    assert build["dataset_hash"] == gamedata.meta.dataset_hash
    assert len(build["slots"]) == 8
    assert build["slots"][0]["name"] == "Serration"
    assert build["slots"][1]["mod"] is None
    assert build["bonus_element"] == {"damage_type": "heat", "share": 0.6}
    assert build["dps"]["direct_burst"] > 0
    share = next(a for a in build["assumptions"] if a["id"] == "bonus_element_share")
    assert share["source"]["url"].endswith("/Kuva_Weapons")


@pytest.mark.parametrize(
    ("body", "status", "code", "field"),
    [
        ({"weapon": "nope"}, 404, "unknown_weapon", "weapon"),
        ({"weapon": "soma-prime", "mods": ["/x"]}, 422, "unknown_mod", "mods[0]"),
        ({"weapon": "soma-prime", "extra": 1}, 422, "invalid_request", "extra"),
        ({"weapon": "soma-prime", "bonus_element": "heat"}, 422, "no_bonus_element", None),
    ],
)
def test_rejected_requests(
    client: TestClient, body: dict[str, object], status: int, code: str, field: str | None
) -> None:
    response = client.post("/api/calc", json=body)
    assert response.status_code == status
    error = response.json()
    assert error["code"] == code
    if field:
        assert error["field"] == field


def test_body_size_limit(client: TestClient) -> None:
    response = client.post("/api/calc", content=b"{" + b" " * 5000 + b"}")
    assert response.status_code == 413
    assert response.json()["code"] == "body_too_large"


def test_spa_routes_get_index(tmp_path: Path, gamedata: GameData) -> None:
    (tmp_path / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    client = TestClient(create_app(web_dist=tmp_path, data=gamedata))
    assert "root" in client.get("/w/soma-prime").text
    assert client.get("/api/nothing").status_code == 404


def test_startup_loads_committed_gamedata(tmp_path: Path) -> None:
    with TestClient(create_app(web_dist=tmp_path / "missing")) as client:
        assert client.post("/api/calc", json={"weapon": "soma-prime"}).status_code == 200


def test_unmodelled_effects_are_listed(client: TestClient, gamedata: GameData) -> None:
    body = {"weapon": "soma-prime", "mods": [_id(gamedata, "Lasting Purity")]}
    ids = {a["id"] for a in client.post("/api/calc", json=body).json()["assumptions"]}
    assert "not_modelled" in ids


def test_invalid_json_has_no_field(client: TestClient) -> None:
    response = client.post(
        "/api/calc", content=b"{nope", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["field"] is None


def test_incarnon_build_with_perks(client: TestClient) -> None:
    body = {"weapon": "soma-prime", "perks": ["Fortifying Bloodshed"]}
    build = client.post("/api/calc", json=body).json()
    assert build["form"] == "incarnon"
    assert build["perks"] == ["Fortifying Bloodshed"]
    assert build["arsenal"]["multishot"] == 8


def test_perk_for_the_other_form_is_named(client: TestClient) -> None:
    body = {"weapon": "torid", "perks": ["Extended Volley"]}
    texts = [a["text"] for a in client.post("/api/calc", json=body).json()["assumptions"]]
    assert "No effect in incarnon form: Extended Volley" in texts


def test_aoe_parts_and_row_notes_are_stated(client: TestClient) -> None:
    def ids(slug: str) -> set[str]:
        build = client.post("/api/calc", json={"weapon": slug}).json()
        return {x["id"] for x in build["assumptions"]}

    assert "aoe_full" in ids("atomos")
    assert "incarnon_note" in ids("onos")


def test_headshot_assumption_and_source(client: TestClient) -> None:
    build = client.post("/api/calc", json={"weapon": "latron-prime"}).json()
    assert build["headshot"]["source"]["url"].endswith("/Incarnon_Evolutions")
    assert "headshot" in {a["id"] for a in build["assumptions"]}
    rubico = client.post("/api/calc", json={"weapon": "rubico-prime"}).json()
    assert rubico["headshot"] == {"reason": "Sniper rifles are aimed at heads", "source": None}
    assert client.post("/api/calc", json={"weapon": "braton-prime"}).json()["headshot"] is None


def test_head_dps_and_stacks(client: TestClient, gamedata: GameData) -> None:
    body = {"weapon": "rubico-prime", "mods": [_id(gamedata, "Galvanized Scope")]}
    build = client.post("/api/calc", json=body).json()
    head = build["dps"]["head"]
    assert head["head"] == "Grineer humanoid head" and head["critical"] is True
    assert head["max_stacks"] > head["zero_stacks"] > build["dps"]["direct_burst"]
    assert head["triggered"] == ["Galvanized Scope"]
    assert "head_stacks" in {a["id"] for a in build["assumptions"]}
    assert client.post("/api/calc", json={"weapon": "braton-prime"}).json()["dps"]["head"] is None


def test_combat_against_every_representative_enemy(client: TestClient, gamedata: GameData) -> None:
    build = client.post("/api/calc", json={"weapon": "rubico-prime"}).json()
    combat = build["combat"]
    assert combat["level"] == 120 and combat["cap_s"] == 10
    assert len(combat["enemies"]) == len(gamedata.enemies)
    by_name = {e["name"]: e for e in combat["enemies"]}
    assert by_name["Lancer"]["target"] == "Head"  # sniper: aimed at heads
    assert by_name["Lumbering Fragment"]["target"] == "Body"  # no headshot spot
    assert {f["faction"] for f in combat["factions"]} == {e.faction for e in gamedata.enemies}
    assert {"combat", "armor"} <= {a["id"] for a in build["assumptions"]}
    body = client.post("/api/calc", json={"weapon": "soma-prime"}).json()["combat"]
    assert {e["target"] for e in body["enemies"]} == {"Body"}
