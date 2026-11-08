import pytest

from app.domain.direct_bonus import DirectBonus, bonus, damage_factor
from app.domain.effects import DamageType as D
from app.domain.effects import Effect, Operation, Stat
from app.domain.hit import AttackStats, modded_hit, with_direct_bonus


def test_bonus_per_status_type_and_stack() -> None:
    """Saved Galvanized_Aptitude: 2 stacks x 2 status types -> +160%."""
    assert bonus(0.4, 2, 2) == pytest.approx(1.6)


def test_adding_and_multiplying_examples() -> None:
    """Saved Condition_Overload_(Mechanic), Math: Serration +165% with +80% CO ->
    adding 1 + 1.65 + 0.8, multiplying (1 + 1.65) x (1 + 0.8)."""
    assert damage_factor(DirectBonus.ADDING, 2.65, 0.8) == pytest.approx(3.45)
    assert damage_factor(DirectBonus.MULTIPLYING, 2.65, 0.8) == pytest.approx(2.65 * 1.8)
    assert damage_factor(DirectBonus.NONE, 2.65, 0.8) == pytest.approx(2.65)


def test_galvanized_aptitude_page_example() -> None:
    """Saved Galvanized_Aptitude: 100 base, Serration, 2 stacks, one status type -> the next
    hit deals 100 x (1 + 1.65 + 0.8) = 345."""
    base = AttackStats({D.IMPACT: 100}, 0, 1, 0, 1)
    hit = modded_hit(base, [(Effect(stat=Stat.DAMAGE, value=1.65), 1.65)])
    assert hit.projectile_damage == pytest.approx(265)
    boosted = with_direct_bonus(hit, DirectBonus.ADDING, bonus(0.4, 2, 1))
    assert boosted.projectile_damage == pytest.approx(345)


def test_bonus_reaches_the_dot_seed() -> None:
    """Saved Condition_Overload_(Mechanic): Electricity procs are generated from the
    bonused hit, so the DoT seed takes the same factor as the direct damage."""
    base = AttackStats({D.ELECTRICITY: 100}, 0, 1, 0, 1)
    boosted = with_direct_bonus(modded_hit(base, []), DirectBonus.MULTIPLYING, 0.8)
    assert boosted.projectile_damage == pytest.approx(180)
    assert boosted.modded_base == pytest.approx(180)


def test_adding_bonus_survives_a_zero_damage_multiplier() -> None:
    """-100% damage leaves only the adding bonus: base x (0 + 0.8)."""
    base = AttackStats({D.IMPACT: 100}, 0, 1, 0, 1)
    hit = modded_hit(base, [(Effect(stat=Stat.DAMAGE, value=-1.0), -1.0)])
    assert hit.projectile_damage == pytest.approx(0)
    boosted = with_direct_bonus(hit, DirectBonus.ADDING, 0.8)
    assert boosted.projectile_damage == pytest.approx(80)
    assert boosted.modded_base == pytest.approx(80)


def test_none_leaves_the_hit_unchanged() -> None:
    base = AttackStats({D.IMPACT: 100}, 0, 1, 0, 1)
    hit = modded_hit(base, [(Effect(stat=Stat.DAMAGE, value=1.65), 1.65)])
    boosted = with_direct_bonus(hit, DirectBonus.NONE, 0.8)
    assert boosted.damage == hit.damage
    assert boosted.modded_base == hit.modded_base


def test_adding_joins_after_separate_damage_factors() -> None:
    """Saved Condition_Overload_(Mechanic), Math (adding): (base x damage bonuses x other
    multipliers) + (base x CO). Serration +165% and a separate x1.5 with +80% CO ->
    100 x (2.65 x 1.5 + 0.8) = 477.5."""
    base = AttackStats({D.IMPACT: 100}, 0, 1, 0, 1)
    separate = Effect(stat=Stat.DAMAGE, value=1.5, operation=Operation.MULTIPLY)
    hit = modded_hit(base, [(Effect(stat=Stat.DAMAGE, value=1.65), 1.65), (separate, 1.5)])
    boosted = with_direct_bonus(hit, DirectBonus.ADDING, 0.8)
    assert boosted.projectile_damage == pytest.approx(477.5)


def test_second_call_raises() -> None:
    """Two sources stack additively: the caller sums them, so a second call is a bug."""
    base = AttackStats({D.IMPACT: 100}, 0, 1, 0, 1)
    once = with_direct_bonus(modded_hit(base, []), DirectBonus.MULTIPLYING, 0.4)
    with pytest.raises(ValueError, match="already applied"):
        with_direct_bonus(once, DirectBonus.MULTIPLYING, 0.4)
