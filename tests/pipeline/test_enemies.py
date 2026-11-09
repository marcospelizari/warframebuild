import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.domain.effects import DamageType
from app.gamedata import store
from app.pipeline.build import build
from app.pipeline.errors import RefreshError
from app.pipeline.refresh import Paths
from app.pipeline.sources import wiki_damage_types

ROOT = Path(__file__).resolve().parents[2]
LANCER = "/Lotus/Types/Enemies/Grineer/AIWeek/RifleLancer"


def test_fixture_enemies_at_steel_path_level(paths: Paths) -> None:
    data = build(paths.raw, paths.reference)
    by_name = {e.name: e for e in data.enemies}
    lancer, crewman = by_name["Lancer"], by_name["Crewman"]
    assert lancer.level == 120 and lancer.faction == "Grineer"
    assert lancer.health == pytest.approx(100 * (1 + 10.7332 * 119**0.72) * 2.5, rel=1e-5)
    assert lancer.armor == pytest.approx(100 * (1 + 0.4 * 119**0.75), rel=1e-5)  # no SP bonus
    assert lancer.shield == 0 and crewman.armor == 0
    assert crewman.shield == pytest.approx(120 * (1 + 2 * 119**0.76) * 2.5, rel=1e-5)
    assert (lancer.head.multiplier, lancer.head.critical) == (3.0, True)  # type: ignore[union-attr]
    assert crewman.head is not None and not crewman.head.critical  # Head (3x)*
    assert lancer.source == "Module:Enemies/data/grineer"
    assert {f.faction: f.modifiers for f in data.factions}["Grineer"] == {DamageType.IMPACT: 1.5}


def _edit(paths: Paths, change: Callable[[dict[str, Any]], None]) -> None:
    table = paths.reference / "enemies.json"
    data = json.loads(table.read_text())
    change(data)
    table.write_text(json.dumps(data))


def _lancer(d: dict[str, Any]) -> dict[str, Any]:
    return d["enemies"][LANCER]  # type: ignore[no-any-return]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: _lancer(d).update({"name": "Elite Lancer"}), "name"),
        (lambda d: d["enemies"].update({"/Nope": _lancer(d)}), "0 module entries"),
        (lambda d: _lancer(d).pop("verified"), "verified"),
        (lambda d: _lancer(d).update({"armor": 1}), "keys"),
        (lambda d: _lancer(d).update({"body_parts_line": 470}), "is not Lancer"),
        (lambda d: _lancer(d)["head"].update({"multiplier": 2}), "page gives"),
        (lambda d: _lancer(d)["head"].update({"critical": False}), "page gives"),
        (lambda d: _lancer(d)["head"].update({"part": "Neck"}), "no headshot spot"),
        (lambda d: _lancer(d).update({"head": None}), "lists a headshot spot"),
        (lambda d: d.update({"level": 0}), "level"),
    ],
)
def test_invalid_rows_fail(
    paths: Paths, change: Callable[[dict[str, Any]], None], message: str
) -> None:
    _edit(paths, change)
    with pytest.raises(RefreshError, match=message):
        build(paths.raw, paths.reference)


def test_overguard_enemy_fails(paths: Paths) -> None:
    module = paths.raw / "wiki/Module_Enemies_grineer.lua"
    module.write_text(module.read_text().replace("BaseLevel = 1", "BaseLevel = 1, Overguard = 22"))
    with pytest.raises(RefreshError, match="Overguard"):
        build(paths.raw, paths.reference)


def test_malformed_stat_fails_only_for_a_used_enemy(paths: Paths) -> None:
    module = paths.raw / "wiki/Module_Enemies_corpus.lua"
    unused = '\t["Unused"] = { General = { InternalName = "/Unused" }, Stats = { Armor = "?" } },\n'
    module.write_text(module.read_text().replace("return {\n", "return {\n" + unused))
    build(paths.raw, paths.reference)
    module.write_text(module.read_text().replace("Health = 90", 'Health = "?"'))
    with pytest.raises(RefreshError, match="Crewman: `Health` must be a number"):
        build(paths.raw, paths.reference)


def test_faction_without_modifiers_fails(paths: Paths) -> None:
    (paths.raw / "wiki/Impact_Damage.wikitext").write_text("stub")
    with pytest.raises(RefreshError, match="no damage modifiers for 'Grineer'"):
        build(paths.raw, paths.reference)


def test_faction_without_a_curve_fails(paths: Paths) -> None:
    table = paths.reference / "enemy_scaling.json"
    data = json.loads(table.read_text())
    data["shield"] = [r for r in data["shield"] if "Corpus" not in r["factions"]]
    table.write_text(json.dumps(data))
    with pytest.raises(RefreshError, match="no shield curve for Corpus"):
        build(paths.raw, paths.reference)


def test_efficacy_colour_must_match_the_value(tmp_path: Path) -> None:
    for stem in wiki_damage_types.PAGES:
        (tmp_path / f"{stem}.wikitext").write_text("")
    (tmp_path / "Heat_Damage.wikitext").write_text("'''{{text|green|x0.5}}''' damage to Grineer")
    with pytest.raises(RefreshError, match="colour"):
        wiki_damage_types.load(tmp_path)


def test_committed_enemies_match_the_table() -> None:
    """The fixtures hold two enemies: every row is checked against the committed gamedata/."""
    data = store.load(ROOT / "gamedata")
    table = json.loads((ROOT / "reference/enemies.json").read_text())
    enemies = {e.unique_name: e for e in data.enemies}
    assert enemies.keys() == table["enemies"].keys()
    for uid, row in table["enemies"].items():
        e = enemies[uid]
        assert e.name == row["name"] and e.level == table["level"]
        assert (e.head.model_dump() if e.head else None) == row["head"], e.name
    factions = {f.faction for f in data.factions}
    assert {e.faction for e in data.enemies} <= factions
