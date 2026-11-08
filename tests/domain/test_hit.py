import pytest

from app.domain.effects import DamageType as D
from app.domain.effects import Effect, Faction, Operation, Stat
from app.domain.hit import AttackStats, modded_hit

BASE = AttackStats(
    damage={D.IMPACT: 30, D.PUNCTURE: 30, D.SLASH: 40},
    critical_chance=0.5,
    critical_multiplier=2.0,
    status_chance=0.1,
    multishot=1,
)


def b(stat: Stat, value: float, **kw: object) -> tuple[Effect, float]:
    return Effect.model_validate({"stat": stat, "value": value, **kw}), value


def test_arsenal_total_formula() -> None:
    """Saved Damage/Calculation, Total Damage: base x (1 + elements + physical) x
    (1 + damage) x multishot; quantized composition 103.125 before bonuses."""
    hit = modded_hit(BASE, [b(Stat.DAMAGE, 1.65), b(Stat.MULTISHOT, 0.9)])
    assert hit.arsenal_total == pytest.approx(103.125 * 2.65 * 1.9)


def test_average_shot_with_crit_faction_and_headshot() -> None:
    bonuses = [
        b(Stat.CRITICAL_CHANCE, 1.5),
        b(Stat.CRITICAL_DAMAGE, 1.2),
        b(Stat.FACTION_DAMAGE, 1.3, operation=Operation.MULTIPLY, faction=Faction.GRINEER),
    ]
    hit = modded_hit(BASE, bonuses)
    assert hit.critical_chance == pytest.approx(1.25)
    assert hit.critical_multiplier == pytest.approx(4.4)
    crit_avg = 1 + 1.25 * (4.4 - 1)
    assert hit.average_shot() == pytest.approx(103.125 * crit_avg)
    assert hit.average_shot(Faction.GRINEER) == pytest.approx(103.125 * crit_avg * 1.3)
    assert hit.average_shot(Faction.CORPUS) == pytest.approx(103.125 * crit_avg)
    headcrit_avg = 1 + 1.25 * (2 * 4.4 - 1)
    assert hit.average_shot(headshot=3.0, headcrit=True) == pytest.approx(
        103.125 * 3.0 * headcrit_avg
    )


def test_elements_follow_slot_order() -> None:
    heat = b(Stat.ELEMENT, 0.9, damage_type=D.HEAT)
    cold = b(Stat.ELEMENT, 0.9, damage_type=D.COLD)
    toxin = b(Stat.ELEMENT, 0.9, damage_type=D.TOXIN)
    assert set(modded_hit(BASE, [heat, cold, toxin]).damage) >= {D.BLAST, D.TOXIN}
    assert set(modded_hit(BASE, [heat, toxin, cold]).damage) >= {D.GAS, D.COLD}


def test_vigilante_upgrade_chance_capped_at_one() -> None:
    hit = modded_hit(BASE, [b(Stat.CRIT_TIER_UPGRADE, 0.6), b(Stat.CRIT_TIER_UPGRADE, 0.6)])
    assert hit.crit_upgrade_chance == 1.0
