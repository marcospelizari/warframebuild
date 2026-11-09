import pytest

from app.domain.enemy_scaling import Curve, Scaling, f32

# Grineer health and armor curves (saved Enemy_Level_Scaling:111-116, :268-270).
HEALTH = Scaling(Curve(0.015, 2.12), Curve(10.7332, 0.72), 70, 80)
ARMOR = Scaling(Curve(0.005, 1.75), Curve(0.4, 0.75), 70, 80)


def test_base_level_keeps_the_base_value() -> None:
    assert HEALTH.multiplier(0) == 1.0
    assert HEALTH.multiplier(-5) == 1.0  # below the base level


def test_lower_curve_below_the_transition_and_upper_curve_above() -> None:
    assert HEALTH.multiplier(50) == Curve(0.015, 2.12).at(50)
    assert HEALTH.multiplier(119) == Curve(10.7332, 0.72).at(119)


def test_transition_blends_the_two_curves() -> None:
    low, high = Curve(0.015, 2.12).at(75), Curve(10.7332, 0.72).at(75)
    assert HEALTH.multiplier(75) == pytest.approx((low + high) / 2, rel=1e-6)  # s = 0.5


def test_lancer_at_level_120() -> None:
    """Lancer: 100 health, 100 armor, base level 1 (saved Module_Enemies_grineer)."""
    assert HEALTH.value(100, 119) == pytest.approx(100 * (1 + 10.7332 * 119**0.72), rel=1e-5)
    assert ARMOR.value(100, 119) == pytest.approx(100 * (1 + 0.4 * 119**0.75), rel=1e-5)


def test_values_are_binary32() -> None:
    assert f32(0.1) != 0.1
    assert f32(HEALTH.value(100, 119)) == HEALTH.value(100, 119)
