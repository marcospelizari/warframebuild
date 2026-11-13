from app.domain.effects import Stat
from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.builds import weapon_builds
from app.optimize.candidates import pool
from app.optimize.scoring import (
    best_primer,
    build_loadout,
    combat_objective,
    element_starts,
    primer_objective,
)
from app.optimize.search import rounded
from app.optimize.variants import elements

BUDGET = 20


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _mod(data: GameData, unique_name_or_name: str) -> Mod:
    return next(m for m in data.mods.mods if unique_name_or_name in (m.unique_name, m.name))


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


def test_why_this_mod_rescores_the_build_without_it(gamedata: GameData) -> None:
    """F8: one entry per mod, exilus and arcane; the rest kept as is (no new search)."""
    soma = _weapon(gamedata, "Soma Prime")
    rec = weapon_builds(gamedata, soma, BUDGET).variants[0].recommended
    keys = [*rec.mods, *([rec.exilus] if rec.exilus else []), *([rec.arcane] if rec.arcane else [])]
    assert sorted(rec.without) == sorted(keys)
    first, *rest = (gamedata.mod_by_id[m] for m in rec.mods)
    exilus = gamedata.mod_by_id[rec.exilus] if rec.exilus else None
    arcane = gamedata.arcane_by_id[rec.arcane] if rec.arcane else None
    perks = [p for p in gamedata.incarnon_by_id[soma.unique_name].perks if p.name in rec.perks]
    lo = build_loadout(gamedata, soma, rest, exilus, (arcane, *perks), None)
    assert rec.without[first.unique_name] == rounded(combat_objective(gamedata)(lo))


def test_max_build_has_why_values_too(gamedata: GameData) -> None:
    out = weapon_builds(gamedata, _weapon(gamedata, "Soma Prime"), BUDGET).variants[0].max
    assert set(out.without) == {*out.mods, *([out.exilus] if out.exilus else [])} | (
        {out.arcane} if out.arcane else set()
    )


def test_every_stored_build_carries_shard_advice(gamedata: GameData) -> None:
    """G91: shards beside the build, scored in the build's own metric; mods unchanged."""
    v = weapon_builds(gamedata, _weapon(gamedata, "Soma Prime"), BUDGET).variants[0]
    builds = [v.max, v.recommended, *v.factions.values(), v.primer]
    for b in builds:
        assert b is not None and b.shards is not None
    assert v.recommended.shards and v.recommended.shards.normal[0].score > v.recommended.score


def test_every_variant_gets_a_primer_build(gamedata: GameData) -> None:
    """G49: every gun, every optimized element; no faction mods, no enemy costs."""
    soma = weapon_builds(gamedata, _weapon(gamedata, "Soma Prime"), BUDGET)
    primer = soma.variants[0].primer
    assert primer is not None and primer.costs == {} and primer.score >= 0
    assert primer.status in ("optimal", "best_found") and primer.without
    effects = [e for m in primer.mods for e in _mod(gamedata, m).effects.effects]
    assert not any(e.stat == Stat.FACTION_DAMAGE for e in effects)
    hind = weapon_builds(gamedata, _weapon(gamedata, "Kuva Hind"), BUDGET)
    assert all(v.primer is not None for v in hind.variants)


def test_primer_search_beats_a_plain_damage_build(gamedata: GameData) -> None:
    soma = _weapon(gamedata, "Soma Prime")
    found = best_primer(gamedata, soma, budget=200)
    plain = build_loadout(gamedata, soma, [_mod(gamedata, "Serration")], None, ())
    assert found.score > primer_objective(gamedata)(plain)


def test_primer_starts_cover_every_element_combination(gamedata: GameData) -> None:
    soma = _weapon(gamedata, "Soma Prime")
    mods = pool(soma, gamedata.mods.mods, gamedata.mods.sets, primer=True).mods
    starts = element_starts(mods)
    assert len(starts) == 15  # 4 elements: 1 + 4 + 6 + 4 combinations, most first
    assert [len(s) for s in starts] == sorted((len(s) for s in starts), reverse=True)
    kinds = [{e.damage_type for m in s for e in m.effects.effects} for s in starts]
    assert all(len(k) == len(s) for k, s in zip(kinds, starts, strict=True))  # one per element
