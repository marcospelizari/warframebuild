import pytest

from app.domain.damage import element_bonuses
from app.domain.effects import DamageType as D
from app.domain.effects import FireRateBoost
from app.domain.elements import Part
from app.domain.status import (
    CrowdControl,
    blast_detonation,
    blast_hits,
    blast_proc,
    boosted,
    chance_of_at_least_one,
    combined_chance,
    dot_seed,
    dot_tick,
    dot_ticks,
    expected_procs,
    heat_ticks,
    proc_shares,
)


def test_proc_shares_example() -> None:
    """Saved Status_Effect, Damage Distribution: 20/5/10/25/50 -> 18.18/4.55/9.09/22.73/45.45%."""
    shares = proc_shares({D.IMPACT: 20, D.PUNCTURE: 5, D.SLASH: 10, D.HEAT: 25, D.CORROSIVE: 50})
    assert shares[D.IMPACT] == pytest.approx(0.1818, abs=1e-4)
    assert shares[D.CORROSIVE] == pytest.approx(0.4545, abs=1e-4)


def test_expected_procs_with_forced() -> None:
    """Saved Status_Effect: average procs = multishot x (forced procs + status chance)."""
    procs = expected_procs(1.5, {D.HEAT: 0.5, D.IMPACT: 0.5}, [D.IMPACT, CrowdControl.KNOCKDOWN])
    assert procs == {D.HEAT: 0.75, D.IMPACT: 1.75, CrowdControl.KNOCKDOWN: 1.0}


def test_at_least_one_proc_above_100_percent() -> None:
    assert chance_of_at_least_one(0.4, 0.5) == pytest.approx(0.2)
    assert chance_of_at_least_one(1.5, 0.5) == pytest.approx(1 - 0.5 * (1 - 0.25))


@pytest.mark.parametrize(
    "chances,expected", [([0.3, 0.35], 0.545), ([0.3, 0.7], 0.79), ([0.3], 0.3)]
)
def test_hunter_munitions_and_internal_bleeding(chances: list[float], expected: float) -> None:
    """Saved Hunter_Munitions / Internal_Bleeding: drawn independently, one Slash at most:
    54.5% (fire rate >= 2.5) or 79% (below)."""
    assert combined_chance(chances) == pytest.approx(expected)


def test_internal_bleeding_threshold_is_strict() -> None:
    """Saved Internal_Bleeding: 'If the weapon's fire rate is exactly 2.5 it won't count'."""
    boost = FireRateBoost(below=2.5, factor=2)
    assert boosted(0.35, boost, 2.5) == 0.35
    assert boosted(0.35, boost, 2.4) == 0.7


@pytest.mark.parametrize(
    "seed,damage_type,element,faction,expected",
    [
        (40, D.HEAT, 0.6, 1.0, 32.8),  # Supra Vandal + Thermite Rounds
        (40, D.ELECTRICITY, 1.5, 1.0, 51.25),
        (40 * 1.55, D.TOXIN, 2.25, 1.55, 158.68),  # Primed Bane of Orokin
        (40, D.GAS, 0.0, 1.0, 20.5),
        (40 * 1.55, D.SLASH, 0.0, 1.55, 34.18),
        (40 + 80.0195389, D.HEAT, 0.6, 1.0, 96.8156357),  # two pooled Heat seeds
    ],
)
def test_dot_tick_examples(
    seed: float, damage_type: D, element: float, faction: float, expected: float
) -> None:
    """Saved Damage/Calculation, Damage Over Time: (sum of seeds + 1) x C x M."""
    assert dot_tick(seed, damage_type, element, faction) == pytest.approx(expected, abs=0.01)


def test_dot_seed_and_status_damage() -> None:
    seed = dot_seed(100 * 2.65, 1.0, 1.3)
    assert dot_tick(seed, D.SLASH, faction=1.3, status_damage=0.9) == pytest.approx(
        (100 * 2.65 * 1.3 + 1) * 0.35 * 1.3 * 1.9
    )


def test_slash_ignores_element_bonus() -> None:
    assert dot_tick(40, D.SLASH, element_bonus=5.0) == pytest.approx(41 * 0.35)


def test_tick_counts() -> None:
    """Saved Damage_over_Time + Status_Effect: 6 ticks base; Hunter Track 11.4 s -> 11."""
    assert dot_ticks(D.SLASH, 0.0) == 6
    assert dot_ticks(D.SLASH, 0.9) == 11
    assert dot_ticks(D.ELECTRICITY, 0.0) == 6
    assert dot_ticks(D.GAS, 0.9) == 12


def test_dot_element_bonus_is_per_literal_type() -> None:
    """Saved Damage_over_Time: Gas DoT is not buffed by its Heat + Toxin mods."""
    mods = [Part(D.HEAT, 0.9), Part(D.TOXIN, 0.9), Part(D.GAS, 0.6)]
    assert element_bonuses(mods) == {D.HEAT: 0.9, D.TOXIN: 0.9, D.GAS: 0.6}


def test_blast_proc_per_the_blast_page() -> None:
    """Blast_Damage:30-44: 0.3 x modded base (faction in it) x crit/body part x faction again
    x (1 + status damage); at least 1 (Calculation:644)."""
    assert blast_proc(100, 2.0 * 1.3, 1.3, 0.5) == pytest.approx(0.3 * 100 * 2.6 * 1.3 * 1.5)
    assert blast_proc(2, 1.0) == 1.0
    assert blast_detonation([100] * 10) == 3000  # on other enemies only (Blast_Damage:23)


def test_blast_stacks_hit_after_their_fuse() -> None:
    hits = blast_hits([(0.0, 1.0, 30.0), (1.0, 1.0, 30.0)], fuse=1.5)
    assert hits == [(1.5, 30.0), (2.5, 30.0)]
    longer = blast_hits([(0.0, 1.0, 30.0)], fuse=1.5 * 2)  # +100% status duration
    assert longer == [(3.0, 30.0)]


def test_ten_blast_stacks_hit_the_target_at_once_for_their_own_damage() -> None:
    """Blast_Damage:21, :23, :59: 10 hits of 30% at once; the 3x burst is not on the target."""
    stacks = [(0.1 * i, 1.0, 30.0) for i in range(10)]
    [(at, damage)] = blast_hits(stacks, fuse=1.5)
    assert at == pytest.approx(0.9) and damage == pytest.approx(300.0)  # not 3 x 300
    [(at, damage)] = blast_hits([(0.0, 0.6, 30.0)], fuse=1.5)
    assert at == 1.5 and damage == pytest.approx(18.0)  # expected stacks below one


def test_heat_pools_into_one_tick_that_grows_with_refreshed_stacks() -> None:
    """Heat_Damage:66: one tick per second from 1 s after the first proc; each proc adds its
    seed and refreshes all; the +1 counts once (Damage/Calculation: Heat example)."""
    procs = [(0.5, 40.0, 1.0), (1.6, 80.0, 1.0)]
    ticks = heat_ticks(procs, 0.5 * 1.6, life=6.0, refreshed=True, until=10.0)
    assert ticks[0] == pytest.approx((1.5, (40 + 1) * 0.8))  # the second proc lands later
    assert ticks[1] == pytest.approx((2.5, (40 + 80 + 1) * 0.8))  # 96.8, the page's example
    assert ticks[-1][0] == pytest.approx(7.5)  # the burn ends 6 s after the last proc


def test_heat_without_refresh_drops_old_stacks() -> None:
    procs = [(0.0, 10.0, 1.0), (5.0, 10.0, 1.0)]
    ticks = dict(heat_ticks(procs, 1.0, life=2.0, refreshed=False, until=10.0))
    assert ticks[1.0] == pytest.approx(11.0)
    assert 3.0 not in ticks  # first burn over, second not yet
    assert ticks[6.0] == pytest.approx(11.0)


def test_heat_expected_procs_below_one_scale_the_plus_one() -> None:
    ticks = heat_ticks([(0.0, 4.0, 0.25)], 1.0, life=6.0, refreshed=True, until=2.0)
    assert ticks[0] == pytest.approx((1.0, 4.0 + 0.25))
