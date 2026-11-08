import pytest

from app.domain.direct_bonus import DirectBonus, bonus, damage_factor
from app.domain.effects import DamageType as D
from app.domain.effects import Effect, Stat
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
