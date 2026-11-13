import pytest

from app.domain.combat import (
    CAP_S,
    INDEX,
    TYPES,
    Event,
    Target,
    armor_reduction,
    effective_hp,
    fight,
    geometric_mean,
    neutral_dps,
)
from app.domain.effects import DamageType


def _vec(**damage: float) -> list[float]:
    out = [0.0] * len(TYPES)
    for name, v in damage.items():
        out[INDEX[DamageType(name)]] = v
    return out


def _event(
    t: float,
    armored: list[float] | None = None,
    unarmored: list[float] | None = None,
    **kw: float,
) -> Event:
    return Event(
        time=t,
        armored=armored or _vec(),
        unarmored=unarmored or _vec(),
        armor_kept=kw.get("armor_kept", 1.0),
        viral=kw.get("viral", 1.0),
        magnetic=kw.get("magnetic", 1.0),
    )


def _target(health: float, shield: float = 0, armor: float = 0, **mods: float) -> Target:
    modifiers = [mods.get(t.value, 1.0) for t in TYPES]
    return Target(health=health, shield=shield, armor=armor, modifiers=modifiers)


def test_armor_reduction_per_the_armor_page() -> None:
    """Armor:35: 0.9 x sqrt(armor / 2700), 90% at the 2,700 cap."""
    assert armor_reduction(0) == 0
    assert armor_reduction(2700) == pytest.approx(0.9)
    assert armor_reduction(300) == pytest.approx(0.3)
    assert armor_reduction(10_000) == pytest.approx(0.9)


def test_kill_time_is_the_killing_event() -> None:
    events = [_event(0.5, _vec(impact=60)), _event(1.0, _vec(impact=60))]
    out = fight(events, _target(100))
    assert out.ttk == 1.0 and out.cost == 1.0 and out.removed == 1.0


def test_alive_at_the_cap_costs_cap_over_removed_share() -> None:
    out = fight([_event(1.0, _vec(impact=25))], _target(100))
    assert out.ttk is None and out.removed == pytest.approx(0.25)
    assert out.cost == pytest.approx(CAP_S / 0.25)
    assert fight([], _target(100)).cost == pytest.approx(CAP_S / 0.01)  # floored (C3)


def test_events_after_the_cap_do_not_count() -> None:
    assert fight([_event(CAP_S + 0.1, _vec(impact=500))], _target(100)).ttk is None


def test_armor_reduces_health_damage_only_and_slash_dot_ignores_it() -> None:
    armored = fight([_event(1, _vec(impact=100))], _target(1000, armor=300)).removed
    assert armored == pytest.approx(0.07)  # 100 x (1 - 0.3)
    dot = fight([_event(1, unarmored=_vec(slash=100))], _target(1000, armor=300)).removed
    assert dot == pytest.approx(0.1)
    stripped = fight([_event(1, _vec(impact=100), armor_kept=0.0)], _target(1000, armor=300))
    assert stripped.removed == pytest.approx(0.1)


def test_shield_first_then_spill_into_health() -> None:
    # 150 hits a 100 shield: 50 spills into health (no armor).
    out = fight([_event(1, _vec(impact=150))], _target(100, shield=100))
    assert out.removed == pytest.approx(150 / 200)


def test_toxin_bypasses_the_shield() -> None:
    assert fight([_event(1, _vec(toxin=150))], _target(100, shield=100)).ttk == 1
    blocked = Target(
        health=100, shield=100, armor=0, modifiers=[1.0] * len(TYPES), toxin_bypasses_shield=False
    )
    out = fight([_event(1, _vec(toxin=150))], blocked)  # Treasurer, Hounds
    assert out.ttk is None and out.removed == pytest.approx(150 / 200)


def test_viral_on_health_magnetic_on_shield_and_faction_modifiers() -> None:
    assert fight([_event(1, _vec(impact=10), viral=2.0)], _target(100)).removed == pytest.approx(
        0.2
    )
    shielded = fight([_event(1, _vec(impact=10), magnetic=3.0)], _target(100, shield=100))
    assert shielded.removed == pytest.approx(30 / 200)
    weak = fight([_event(1, _vec(impact=10))], _target(100, impact=1.5))
    assert weak.removed == pytest.approx(0.15)


def test_geometric_mean() -> None:
    assert geometric_mean([1.0, 4.0]) == pytest.approx(2.0)


def test_bleed_is_cinematic_no_armor_and_no_faction_modifier() -> None:
    """Cinematic_Damage:9-13: no damage modifier against any faction, bypasses armor, hits
    shields too."""
    infested = _target(1000, slash=1.5)
    bleed = fight([_event(1, unarmored=_vec(slash=100))], infested)
    assert bleed.removed == pytest.approx(0.1)
    direct = fight([_event(1, _vec(slash=100))], infested)
    assert direct.removed == pytest.approx(0.15)
    shielded = fight([_event(1, unarmored=_vec(slash=100))], _target(1000, shield=1000))
    assert shielded.removed == pytest.approx(100 / 2000)


def test_neutral_dps_counts_viral_and_the_cap() -> None:
    """G80: health only; Viral raises the damage; events after the cap do not count."""
    zero = [0.0] * len(TYPES)
    hit = [100.0, *zero[1:]]
    events = [
        Event(time=1.0, armored=hit, unarmored=zero, armor_kept=1.0, viral=2.0, magnetic=1.0),
        Event(time=2.0, armored=zero, unarmored=hit, armor_kept=1.0, viral=1.0, magnetic=1.0),
        Event(time=CAP_S + 1, armored=hit, unarmored=zero, armor_kept=1.0, viral=1.0, magnetic=1.0),
    ]
    assert neutral_dps(events) == pytest.approx(300 / CAP_S)


def test_effective_hp_matches_the_priming_page() -> None:
    """Priming:37-40, 2700 armor: 1 Corrosive (to 1998) = +125.79%, 10 Corrosive (to 540) =
    +497.51%, 10 Corrosive and 1 Viral = +1095.02%, 10 Viral and 1 Corrosive = +859.61%."""
    plain = effective_hp(1.0, 0.0, 2700)

    def boost(kept: float, viral: float = 1.0) -> float:
        return plain / effective_hp(1.0, 0.0, 2700, armor_kept=kept, viral=viral)

    assert boost(1998 / 2700) == pytest.approx(2.2579, abs=1e-4)
    assert boost(540 / 2700) == pytest.approx(5.9751, abs=1e-4)
    assert boost(540 / 2700, viral=2.0) == pytest.approx(11.9502, abs=1e-4)
    assert boost(1998 / 2700, viral=4.25) == pytest.approx(9.5961, abs=1e-4)
    assert effective_hp(100, 50, 0, magnetic=2.0) == pytest.approx(125)  # shield halved
