from app.gamedata.models import Arcane, Perk, Weapon
from app.gamedata.store import GameData
from app.optimize.scoring import best_combat, choices, combat_mods


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _banes(data: GameData, faction: str | None) -> set[str]:
    mods = combat_mods(data, _weapon(data, "Soma Prime"), faction)
    return {m.name for m in mods if "Bane" in m.name}


def test_faction_mods_only_in_their_own_faction_build(gamedata: GameData) -> None:
    assert _banes(gamedata, None) == set()
    grineer = _banes(gamedata, "Grineer")
    assert grineer and all("Grineer" in n for n in grineer)


def test_choice_slots_hold_the_arcane_and_one_per_evo_tier(gamedata: GameData) -> None:
    soma = _weapon(gamedata, "Soma Prime")
    arcanes, *tiers = choices(gamedata, soma)
    assert arcanes[0] is None
    assert all(isinstance(a, Arcane) and a.category == "primary" for a in arcanes[1:])
    assert len(tiers) == 3  # EVO 2-4
    for tier in tiers:
        assert tier[0] is None
        assert all(isinstance(p, Perk) and p.effects.support == "full" for p in tier[1:])
    names = {p.name for t in tiers for p in t[1:] if p}
    assert "Fresh Havoc" not in names  # unsupported (R6)
    assert "Kinetic Battle" not in names  # no damage effects


def test_guns_without_incarnon_have_only_the_arcane_slot(gamedata: GameData) -> None:
    assert len(choices(gamedata, _weapon(gamedata, "Rubico Prime"))) == 1


def test_combat_search_runs_within_its_budget(gamedata: GameData) -> None:
    result = best_combat(gamedata, _weapon(gamedata, "Rubico Prime"), "Grineer", budget=30)
    assert result.status == "best_found"
    assert result.evaluations == 30
    assert result.score > 0
