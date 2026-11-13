from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import jobs
from app.api.app import create_app
from app.api.rate_limit import RateLimit
from app.api.runner import Runner
from app.gamedata.release import open_current
from app.gamedata.store import GameData
from app.optimize.builds import weapon_builds
from app.optimize.scoring import build_loadout, combat_objective, max_objective
from app.optimize.search import rounded
from tests.api.conftest import GUNS


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData) -> TestClient:
    app = create_app(web_dist=tmp_path / "missing", data=gamedata, releases=tmp_path)
    app.state.rate_limit = RateLimit(rate=1e9, burst=10**9)  # tests below send many requests
    return TestClient(app)


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
    client = TestClient(create_app(web_dist=tmp_path, data=gamedata, releases=tmp_path))
    assert "root" in client.get("/w/soma-prime").text
    assert client.get("/api/nothing").status_code == 404


def test_startup_loads_committed_gamedata(tmp_path: Path) -> None:
    with TestClient(create_app(web_dist=tmp_path / "missing", releases=tmp_path)) as client:
        assert client.post("/api/calc", json={"weapon": "soma-prime"}).status_code == 200


def test_unmodelled_effects_are_listed(client: TestClient, gamedata: GameData) -> None:
    body = {"weapon": "vulkar-wraith", "mods": [_id(gamedata, "Lasting Purity")]}
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


def test_set_bonus_and_compatibility(client: TestClient, gamedata: GameData) -> None:
    body = {"weapon": "soma-prime", "mods": [_id(gamedata, "Vigilante Armaments")]}
    texts = [a["text"] for a in client.post("/api/calc", json=body).json()["assumptions"]]
    assert any("Vigilante set (1/6)" in t for t in texts)
    body = {"weapon": "lenz", "mods": [_id(gamedata, "Split Flights")]}
    error = client.post("/api/calc", json=body).json()
    assert (error["code"], error["field"]) == ("incompatible_mod", "mods[0]")


def test_arcane_and_exilus_are_scored_and_echoed(client: TestClient, gamedata: GameData) -> None:
    arcane = next(a for a in gamedata.arcanes if a.name == "Secondary Surge")
    exilus = next(m for m in gamedata.mods.mods if m.name == "Vile Precision")
    body = {"weapon": "lex-prime", "arcane": arcane.unique_name}
    build = client.post("/api/calc", json=body).json()
    assert build["arcane"] == {"unique_name": arcane.unique_name, "name": "Secondary Surge"}
    assert build["exilus"] is None
    assert build["dps"]["max_score"] > 0
    rifle = client.post("/api/calc", json={"weapon": "soma-prime", "exilus": exilus.unique_name})
    assert rifle.status_code == 200, rifle.json()
    assert rifle.json()["exilus"]["name"] == "Vile Precision"


@pytest.mark.parametrize(
    ("body", "code", "field"),
    [
        ({"weapon": "lex-prime", "arcane": "/x"}, "unknown_arcane", "arcane"),
        ({"weapon": "soma-prime", "exilus": "/x"}, "unknown_mod", "exilus"),
    ],
)
def test_unknown_arcane_or_exilus(
    client: TestClient, body: dict[str, object], code: str, field: str
) -> None:
    response = client.post("/api/calc", json=body)
    assert response.status_code == 422
    assert (response.json()["code"], response.json()["field"]) == (code, field)


def test_exilus_slot_takes_only_exilus_mods(client: TestClient, gamedata: GameData) -> None:
    body = {"weapon": "soma-prime", "exilus": _id(gamedata, "Serration")}
    response = client.post("/api/calc", json=body)
    assert (response.status_code, response.json()["code"]) == (422, "not_exilus")


@pytest.mark.parametrize("gun", ["Soma Prime", "Kuva Hind", "Lex Prime"])
def test_calc_returns_every_stored_score(
    client: TestClient, gamedata: GameData, releases: Path, gun: str
) -> None:
    """E8: each precomputed build through /calc gives its stored score (after `rounded`).
    Guns in the shared test release are read from it, not searched again."""
    weapon = next(w for w in gamedata.weapons if w.name == gun)
    shared = open_current(releases)
    assert shared is not None
    in_release = gun in GUNS
    stored = shared.builds(weapon.slug) if in_release else weapon_builds(gamedata, weapon, 20)
    for v in stored.variants:
        tabs = {"max": v.max, "recommended": v.recommended, **v.factions}
        for tab, b in tabs.items():
            body = {
                "weapon": weapon.slug,
                "mods": b.mods,
                "exilus": b.exilus,
                "arcane": b.arcane,
                "perks": b.perks,
                "bonus_element": v.element,
            }
            response = client.post("/api/calc", json=body)
            assert response.status_code == 200, (tab, response.json())
            out = response.json()
            if tab == "max":
                got = out["dps"]["max_score"]
            elif tab == "recommended":
                got = 1 / out["combat"]["score"]
            else:
                got = 1 / next(f["score"] for f in out["combat"]["factions"] if f["faction"] == tab)
            assert rounded(got) == b.score, (v.element, tab)


def test_calc_matches_the_search_scorer_with_exilus_arcane_and_perk(
    client: TestClient, gamedata: GameData
) -> None:
    """E8 for the choice slots the stored samples above may leave empty."""
    lex = next(w for w in gamedata.weapons if w.name == "Lex Prime")
    mods = [next(m for m in gamedata.mods.mods if m.name == "Hornet Strike")]
    exilus = next(m for m in gamedata.mods.mods if m.name == "Targeting Subsystem")
    arcane = next(a for a in gamedata.arcanes if a.name == "Secondary Surge")
    perk = next(p for p in gamedata.incarnon_by_id[lex.unique_name].perks if p.tier == 2)
    lo = build_loadout(gamedata, lex, mods, exilus, (arcane, perk))
    body = {
        "weapon": lex.slug,
        "mods": [m.unique_name for m in mods],
        "exilus": exilus.unique_name,
        "arcane": arcane.unique_name,
        "perks": [perk.name],
    }
    out = client.post("/api/calc", json=body).json()
    assert out["exilus"]["index"] == 8
    assert rounded(out["dps"]["max_score"]) == rounded(max_objective(gamedata)(lo))
    assert rounded(1 / out["combat"]["score"]) == rounded(combat_objective(gamedata)(lo))


def test_rate_limit_answers_429_with_retry_after(client: TestClient) -> None:
    now = [0.0]
    client.app.state.rate_limit = RateLimit(rate=0.5, burst=2, clock=lambda: now[0])  # type: ignore[attr-defined]
    body = {"weapon": "soma-prime"}
    assert [client.post("/api/calc", json=body).status_code for _ in range(2)] == [200, 200]
    limited = client.post("/api/calc", json=body)
    assert (limited.status_code, limited.json()["code"]) == (429, "rate_limited")
    assert limited.headers["retry-after"] == "2"
    now[0] = 2.0  # one token back
    assert client.post("/api/calc", json=body).status_code == 200


def test_no_free_worker_answers_503_busy(client: TestClient, gamedata: GameData) -> None:
    state = client.app.state  # type: ignore[attr-defined]
    state.served = replace(state.served, runner=Runner(0, 0, 5, False, jobs.load_data, (gamedata,)))
    response = client.post("/api/calc", json={"weapon": "soma-prime"})
    assert (response.status_code, response.json()["code"]) == (503, "busy")
    assert response.headers["retry-after"] == "1"


def test_slow_job_answers_503_timeout(client: TestClient, gamedata: GameData) -> None:
    state = client.app.state  # type: ignore[attr-defined]
    state.served = replace(
        state.served, runner=Runner(1, 0, 1e-6, False, jobs.load_data, (gamedata,))
    )
    response = client.post("/api/calc", json={"weapon": "soma-prime"})
    assert (response.status_code, response.json()["code"]) == (503, "timeout")


def test_calc_runs_in_worker_processes(tmp_path: Path) -> None:
    """Without injected data the app spawns workers that load gamedata/ themselves."""
    with TestClient(create_app(web_dist=tmp_path, releases=tmp_path)) as client:
        assert client.app.state.served.runner._processes  # type: ignore[attr-defined]
        response = client.post("/api/calc", json={"weapon": "soma-prime"})
        assert response.status_code == 200
        bad = client.post("/api/calc", json={"weapon": "soma-prime", "mods": ["/x"]})
        assert (bad.status_code, bad.json()["field"]) == (422, "mods[0]")


def test_combined_elements_carry_their_parts(client: TestClient, gamedata: GameData) -> None:
    mods = [_id(gamedata, "Infected Clip"), _id(gamedata, "Cryo Rounds")]  # toxin, cold
    build = client.post("/api/calc", json={"weapon": "soma-prime", "mods": mods}).json()
    arsenal = build["arsenal"]
    assert "viral" in arsenal["damage"]
    assert arsenal["combined"] == {"viral": ["cold", "toxin"]}
    assert build["forma"] is not None and build["forma"]["used"] <= build["forma"]["capacity"]
