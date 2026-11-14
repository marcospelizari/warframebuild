import pytest

from app.domain.effects import DamageType as D
from app.domain.effects import Effect, Faction, Operation, Stat
from app.domain.headshot import Head
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
    assert hit.average_shot(head=Head(3.0, critical=True)) == pytest.approx(
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


def test_base_damage_bonus_scales_the_base_not_the_multiplier() -> None:
    # Soma Prime 12 base + Fortifying Bloodshed +10 = 22: Impact 2.2 in the arsenal.
    soma = AttackStats(
        damage={D.IMPACT: 1.2, D.PUNCTURE: 4.8, D.SLASH: 6.0},
        critical_chance=0.3,
        critical_multiplier=3.0,
        status_chance=0.1,
        multishot=1.0,
    )
    perk = Effect(stat=Stat.DAMAGE, value=10, operation=Operation.BASE)
    hit = modded_hit(soma, [(perk, 10.0)])
    assert hit.base_total == pytest.approx(22)
    assert hit.damage_multiplier == 1.0
    assert hit.projectile_damage == pytest.approx(22, abs=22 / 32)


def test_weak_point_crit_chance_adds_to_crit_bonuses() -> None:
    """Saved Enemy_Body_Parts: weak-point crit chance is additive with Point Strike."""
    acuity = [
        b(Stat.CRITICAL_CHANCE, 1.5),
        b(Stat.WEAK_POINT_CRITICAL_CHANCE, 3.5),
        b(Stat.WEAK_POINT_DAMAGE, 3.5),
    ]
    hit = modded_hit(BASE, acuity)
    assert hit.critical_chance == pytest.approx(0.5 * 2.5)
    assert hit.head_critical_chance == pytest.approx(0.5 * 6.0)
    assert hit.weak_point_damage == pytest.approx(3.5)
    head = Head(3.0, critical=True)
    crit_avg = 1 + 3.0 * (2 * 2.0 - 1)
    assert hit.average_shot(head=head) == pytest.approx(103.125 * (3 + 1.5 * 3.5) * crit_avg)
    # 1x head: body crit chance, no weak-point bonus and no critical-headshot bonus (saved
    # Critical_Hit:425: "will not benefit from the critical bonus").
    flat_avg = 1 + 1.25 * (2.0 - 1)
    assert hit.average_shot(head=head, flat=True) == pytest.approx(103.125 * flat_avg)


def test_own_headshot_bonus_adds_or_multiplies() -> None:
    """Saved Enemy_Body_Parts: Kuva Chakkhurr's +50% joins the headshot bonuses (Headshot
    Multiplier Bonuses); Cernos Prime's 50% multiplies on top (Notes)."""
    hit = modded_hit(BASE, [b(Stat.HEADSHOT_MULTIPLIER, 0.3)])
    head = Head(3.0, critical=False)
    assert hit.average_shot(head=head, extra_bonus=0.5) == pytest.approx(
        hit.average_shot() * 3 * 1.8
    )
    assert hit.average_shot(head=head, extra_factor=0.5) == pytest.approx(
        hit.average_shot() * 3 * 1.3 * 1.5
    )


def test_flat_crit_chance_after_mods() -> None:
    """Saved Lanka: zoom adds a flat +50 crit chance after mods: 25 x (1 + 1.5) + 50."""
    base = AttackStats(
        damage={D.ELECTRICITY: 100},
        critical_chance=0.25,
        critical_multiplier=2.0,
        status_chance=0.1,
        multishot=1,
    )
    zoom = b(Stat.CRITICAL_CHANCE, 0.5, operation=Operation.ADD)
    hit = modded_hit(base, [b(Stat.CRITICAL_CHANCE, 1.5), zoom])
    assert hit.critical_chance == pytest.approx(1.125)


def test_typed_status_damage_joins_one_status_only() -> None:
    """Saved Archon_Shard:334, :337: Emerald's Toxin status bonus adds to Elementalist."""
    hit = modded_hit(
        BASE, [b(Stat.STATUS_DAMAGE, 0.9), b(Stat.STATUS_DAMAGE, 0.3, damage_type=D.TOXIN)]
    )
    assert hit.status_damage == pytest.approx(0.9)
    assert hit.type_status_damage == {D.TOXIN: pytest.approx(0.3)}
