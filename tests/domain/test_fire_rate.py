from dataclasses import replace

import pytest

from app.domain.fire_rate import (
    Firing,
    effective_fire_rate,
    reload_cycle,
    shooting_share,
    shot_times,
    shots_per_magazine,
)

AUTO = Firing(
    fire_rate=10,
    charge_time=None,
    burst_count=None,
    burst_delay=None,
    bow=False,
    magazine=50,
    ammo_cost=1,
    reload_time=2,
    no_reload=False,
    reload_replaces_shot=False,
)


def test_plain_rate_is_the_modded_rate() -> None:
    assert effective_fire_rate(AUTO, 1.9) == pytest.approx(19)


def test_burston_burst_example() -> None:
    """Saved Fire_Rate: Burston fire rate 5, burst delay 0.061, 3 shots."""
    burston = replace(AUTO, fire_rate=5, burst_count=3, burst_delay=0.061)
    assert effective_fire_rate(burston, 1.0) == pytest.approx(3 / (1 / 5 + 2 * 0.061))


def test_burst_delay_not_slowed_by_negative_bonus() -> None:
    """Saved Fire_Rate: 'Burst Delay is not affected by net negative Fire Rate bonuses'."""
    burston = replace(AUTO, fire_rate=5, burst_count=3, burst_delay=0.061)
    assert effective_fire_rate(burston, 0.5) == pytest.approx(3 / (1 / 2.5 + 2 * 0.061))
    assert effective_fire_rate(burston, 2.0) == pytest.approx(3 / (1 / 10 + 2 * 0.0305))


def test_charge_formula_and_cap() -> None:
    """Saved Calculation: 1 / (modded charge + 1 / modded fire rate); Fire_Rate: charge time
    = base / (1 + bonus), never above 10x base."""
    opticor = replace(AUTO, fire_rate=1, charge_time=2)
    assert effective_fire_rate(opticor, 1.0) == pytest.approx(1 / 3)
    assert effective_fire_rate(opticor, 2.0) == pytest.approx(1 / (1 + 0.5))
    assert effective_fire_rate(opticor, 0.05) == pytest.approx(1 / (20 + 20))


def test_lanka_charge_alone() -> None:
    """Saved Fire_Rate: Lanka has no delay between charged shots -> 1 / charge time."""
    lanka = replace(AUTO, fire_rate=None, charge_time=1.0)
    assert effective_fire_rate(lanka, 1.0) == pytest.approx(1.0)


def test_bow_formula_holds_the_reload() -> None:
    """Saved Fire_Rate: bows 1 / (charge + reload); sustained = burst."""
    paris = replace(AUTO, charge_time=0.5, bow=True, magazine=1, reload_time=0.7)
    rate = effective_fire_rate(paris, 1.0)
    assert rate == pytest.approx(1 / 1.2)
    assert shooting_share(paris, rate) == 1.0


def test_sustained_share() -> None:
    """Saved Calculation: shots / (effective rate x reload + shots)."""
    assert shooting_share(AUTO, 10) == pytest.approx(50 / (10 * 2 + 50))
    beam = replace(AUTO, ammo_cost=0.5)
    assert shooting_share(beam, 10) == pytest.approx(100 / (10 * 2 + 100))


def test_epitaph_and_vectis() -> None:
    """Saved Calculation: Epitaph ignores reload; Vectis subtracts one from the denominator."""
    assert shooting_share(replace(AUTO, no_reload=True, magazine=1), 1.5) == 1.0
    vectis = replace(AUTO, magazine=1, reload_time=1.0, reload_replaces_shot=True)
    assert shooting_share(vectis, 2.0) == pytest.approx(1 / (2.0 * 1.0 + 1 - 1))


def test_no_magazine_never_reloads() -> None:
    assert shooting_share(replace(AUTO, magazine=None), 10) == 1.0


def test_attack_without_ammo_cost_never_reloads() -> None:
    assert shooting_share(replace(AUTO, ammo_cost=0), 10) == 1.0


def _firing(**kw: object) -> Firing:
    base: dict[str, object] = dict(
        fire_rate=2.0,
        charge_time=None,
        burst_count=None,
        burst_delay=None,
        bow=False,
        magazine=3.0,
        ammo_cost=1.0,
        reload_time=1.0,
        no_reload=False,
        reload_replaces_shot=False,
    )
    return Firing(**(base | kw))  # type: ignore[arg-type]


def test_shots_land_at_the_end_of_each_cycle_with_reloads() -> None:
    """G72: the first shot at one interval; an empty magazine adds the reload."""
    assert shot_times(_firing(), 1.0, 4.0) == pytest.approx([0.5, 1.0, 1.5, 3.0, 3.5, 4.0])


def test_reload_in_place_of_an_interval_and_no_reload() -> None:
    assert shot_times(_firing(reload_replaces_shot=True), 1.0, 3.0) == pytest.approx(
        [0.5, 1.0, 1.5, 2.5, 3.0]
    )
    assert shot_times(_firing(no_reload=True), 1.0, 2.0) == pytest.approx([0.5, 1.0, 1.5, 2.0])


def test_charge_weapons_and_bows_fire_first_at_the_charge_time() -> None:
    """G72: the first shot lands when the charge completes; the next after a full cycle."""
    bow = _firing(bow=True, charge_time=0.5, magazine=1.0, reload_time=0.5)  # 1 / (0.5 + 0.5)
    assert shot_times(bow, 1.0, 2.5) == pytest.approx([0.5, 1.5, 2.5])
    charge = _firing(charge_time=1.0, fire_rate=1.0, magazine=None)  # 1 / (1 + 1) = 0.5/s
    assert shot_times(charge, 1.0, 5.0) == pytest.approx([1.0, 3.0, 5.0])
    assert shot_times(charge, 2.0, 2.0) == pytest.approx([0.5, 1.5])  # +100% fire rate


def test_reload_cycle_and_shots_per_magazine() -> None:
    f = _firing()  # 3 shots at 2/s, 1 s reload
    assert shots_per_magazine(f) == 3
    assert reload_cycle(f, 2.0) == pytest.approx(2.5)
    assert reload_cycle(_firing(reload_replaces_shot=True), 2.0) == pytest.approx(2.0)
    assert shots_per_magazine(_firing(no_reload=True)) is None
    assert reload_cycle(_firing(magazine=None), 2.0) is None
    bow = _firing(bow=True, charge_time=0.5, magazine=1.0)
    assert shots_per_magazine(bow) == 1
    assert reload_cycle(bow, 0.8) == pytest.approx(1.25)
