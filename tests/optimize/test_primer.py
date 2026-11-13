import math

import pytest

from app.domain.effects import DamageType
from app.gamedata.models import Mod
from app.gamedata.store import GameData
from app.optimize.candidates import pool
from app.optimize.conditions import resolve
from app.optimize.loadout import Loadout, loadout
from app.optimize.primer import (
    BURST_S,
    DENSITY,
    FOLLOW_S,
    MAX_PRIMED,
    enemies_reached,
    follow_up_times,
    good_primers,
    primed,
    primer_shot,
)
from app.optimize.timeline import Timeline


def _gun(data: GameData, name: str, *mods: str, blast: str | None = None) -> Loadout:
    by_name: dict[str, Mod] = {m.name: m for m in data.mods.mods}
    weapon = next(w for w in data.weapons if w.name == name)
    if blast:
        weapon = weapon.model_copy(update={"blast": blast})  # a reference/blasts.json row
    return loadout(weapon, [by_name[n] for n in mods])


def _soma(data: GameData, *mods: str) -> Loadout:
    return _gun(data, "Soma Prime", *mods)


def test_follow_up_window_starts_when_the_burst_ends() -> None:
    times = follow_up_times()
    assert BURST_S < times[0] < times[-1] < BURST_S + FOLLOW_S


def test_corrosive_and_viral_prime_more_than_plain_damage(gamedata: GameData) -> None:
    """Priming:21-23: Viral and Corrosive are the elements to prime with."""
    plain = primed(_soma(gamedata, "Serration"), gamedata.enemies, gamedata.status_rules)
    corrosive = _soma(gamedata, "Infected Clip", "Stormbringer")
    viral = _soma(gamedata, "Infected Clip", "Cryo Rounds")
    for lo in (corrosive, viral):
        p = primed(lo, gamedata.enemies, gamedata.status_rules)
        assert p.boost > plain.boost >= 1.0
        assert p.status_types > 0
    assert plain.enemies == 1.0 and plain.radius is None  # Soma: no blast


def test_a_burst_wears_off_over_the_follow_up(gamedata: GameData) -> None:
    lo = _soma(gamedata, "Infected Clip", "Stormbringer")
    tl = Timeline(lo, resolve(lo, False), None, None, gamedata.status_rules, until=BURST_S)
    assert tl.times and tl.times[-1] <= BURST_S
    window = gamedata.status_rules.types[DamageType.CORROSIVE].duration_s * tl.duration
    early, late = tl.debuffs_at(BURST_S + 0.1), tl.debuffs_at(tl.times[-1] + window + 0.1)
    assert early.armor_kept < late.armor_kept == pytest.approx(1.0)  # Corrosive expired


def test_heat_armor_comes_back_after_the_last_burning_shot(gamedata: GameData) -> None:
    """Heat_Damage:81: the strip holds while burning, then returns step by step."""
    lo = _soma(gamedata, "Hellfire")
    tl = Timeline(lo, resolve(lo, False), None, None, gamedata.status_rules, until=BURST_S)
    life = gamedata.status_rules.types[DamageType.HEAT].duration_s * tl.duration
    end = tl.times[-1] + life
    kept = [tl.debuffs_at(end + s).armor_kept for s in (-0.1, 1.6, 3.1, 7.0)]
    assert kept == sorted(kept) and kept[0] < kept[-1] == pytest.approx(1.0)


def test_a_blast_primes_the_enemies_around_by_its_radius(gamedata: GameData) -> None:
    """Area_of_Effect:35: every enemy in the blast rolls its own statuses."""
    rules = gamedata.status_rules
    lo = _gun(gamedata, "Torid", "Infected Clip", "Stormbringer", blast="Poison Cloud")
    p = primed(lo, gamedata.enemies, rules)
    assert p.radius == pytest.approx(3.0)
    assert p.enemies == pytest.approx(DENSITY * math.pi * 9)
    assert p.area_boost > 1.0
    assert p.score == pytest.approx((p.boost - 1) + (p.enemies - 1) * (p.area_boost - 1))
    no_row = primed(
        _gun(gamedata, "Torid", "Infected Clip", "Stormbringer"), gamedata.enemies, rules
    )
    assert (no_row.enemies, no_row.area_boost, no_row.radius) == (1.0, 1.0, None)
    assert no_row.boost == pytest.approx(p.boost)  # the target is primed the same


def test_radius_mods_widen_the_blast_up_to_the_crowd_cap(gamedata: GameData) -> None:
    plain = primed(_gun(gamedata, "Lenz", blast="Bubble Collapse"), [], gamedata.status_rules)
    wide = _gun(gamedata, "Lenz", "Primed Firestorm", blast="Bubble Collapse")
    assert plain.radius is not None
    assert primed(wide, [], gamedata.status_rules).radius == pytest.approx(plain.radius * 1.44)
    assert enemies_reached(None) == enemies_reached(0.1) == 1.0
    assert enemies_reached(100.0) == MAX_PRIMED


def test_radius_mods_join_only_the_primer_pool(gamedata: GameData) -> None:
    lenz = next(w for w in gamedata.weapons if w.name == "Lenz")
    sets = gamedata.mods.sets
    names = {m.name for m in pool(lenz, gamedata.mods.mods, sets).mods}
    primer = {m.name for m in pool(lenz, gamedata.mods.mods, sets, primer=True).mods}
    assert "Primed Firestorm" not in names
    assert "Primed Firestorm" in primer and names < primer


def test_the_primer_fires_its_own_shot_when_the_row_names_one(gamedata: GameData) -> None:
    """Epitaph: DE's numbers are the charged shot; the primer fires the uncharged one."""
    lo = _gun(gamedata, "Torid", "Infected Clip", "Stormbringer", blast="Poison Cloud")
    weapon = lo.weapon.model_copy(update={"primer_shot": ["Poison Cloud"]})
    fired = primer_shot(loadout(weapon, []))
    assert [a.name for _, a in fired.parts if a] == ["Poison Cloud"]
    assert primer_shot(lo) is lo  # no shot named: the scored shot


def test_good_primers_need_a_top_score_and_many_status_types() -> None:
    """Marcos 2026-11-13: many elements and statuses make a primer, not an AoE alone."""
    guns = {f"g{i}": (float(i), 5.0) for i in range(20)}  # top 10% = g19, g18
    guns["aoe"] = (100.0, 2.0)  # best score, few statuses
    assert good_primers(guns) == ["g18", "g19"]
    assert good_primers({}) == []
