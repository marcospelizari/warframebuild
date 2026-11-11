from app.gamedata.models import Weapon
from app.gamedata.store import GameData
from app.optimize.builds import weapon_builds
from app.optimize.variants import elements

BUDGET = 20


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _factions(data: GameData) -> set[str]:
    return {e.faction for e in data.enemies}


def test_plain_gun_gets_max_recommended_and_every_faction(gamedata: GameData) -> None:
    out = weapon_builds(gamedata, _weapon(gamedata, "Soma Prime"), BUDGET)
    assert out.elements == []
    [variant] = out.variants
    assert variant.element is None
    assert set(variant.factions) == _factions(gamedata)
    assert variant.max.costs == {}
    assert set(variant.recommended.costs) == {e.unique_name for e in gamedata.enemies}
    for faction, build in variant.factions.items():
        own = {e.unique_name for e in gamedata.enemies if e.faction == faction}
        assert set(build.costs) == own
        assert {k: variant.denominators[k] for k in own} == build.costs
        assert build.status in ("optimal", "best_found")
        assert len(build.mods) <= 8


def test_progenitor_gun_optimizes_the_top_two_elements(gamedata: GameData) -> None:
    hind = _weapon(gamedata, "Kuva Hind")
    out = weapon_builds(gamedata, hind, BUDGET)
    assert [r.rank for r in out.elements] == list(range(1, len(elements(hind)) + 1))
    assert [r.optimized for r in out.elements].count(True) == 2
    first, second = out.variants
    assert [first.element, second.element] == [r.element for r in out.elements[:2]]
    assert first.recommended.score == out.elements[0].searched
    assert first.recommended.score == out.elements[0].what_if  # same mods, same element
    assert first.max.search_scope == [f"elements: top 2 of {len(out.elements)}"]
    for faction, build in second.factions.items():
        assert build.status == "what_if"
        assert build.evaluations == 0
        assert build.mods == first.factions[faction].mods
        assert build.search_scope[0].startswith("what-if:")


def test_stored_builds_carry_a_forma_layout(gamedata: GameData) -> None:
    out = weapon_builds(gamedata, _weapon(gamedata, "Soma Prime"), BUDGET)
    forma = out.variants[0].recommended.forma
    assert forma is not None
    assert forma.used <= forma.capacity
    assert len(forma.regular) == 8
