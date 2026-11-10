import pytest

from app.domain import crit
from app.domain.crit import average_multiplier, non_crit_chance, tier_multiplier, tiers


def test_lenz_point_strike_tiers() -> None:
    """Saved Critical_Hit: Lenz 50% x (1 + 150%) = 125% -> 75% yellow, 25% orange."""
    assert tiers(0.5 * 2.5) == pytest.approx({1: 0.75, 2: 0.25})


def test_orange_multiplier_example() -> None:
    """Same page: Lenz + Vital Sense orange crit = 1 + 2 x (2.0 x 2.2 - 1) = 7.8."""
    assert tier_multiplier(2, 2.0 * 2.2) == pytest.approx(7.8)


def test_critical_headshot_example() -> None:
    """Same page, Critical Headshots: Lanka + Vital Sense, headshot 3.0, orange crit
    = 3.0 x (1 + 2 x (2 x 2.0 x 2.2 - 1))."""
    assert 3.0 * tier_multiplier(2, 2.0 * 2.2, headcrit=True) == pytest.approx(49.8)


@pytest.mark.parametrize("cc,expected", [(0.99, 0.01), (1.0, 0.0), (1.5, 0.0)])
def test_no_non_crit_from_100_percent(cc: float, expected: float) -> None:
    """C1: every hit crits at crit chance >= 100%."""
    assert non_crit_chance(cc) == pytest.approx(expected)
    assert tiers(cc).get(0, 0.0) == pytest.approx(expected)


def test_average_is_linear_in_crit_chance() -> None:
    """Saved Calculation, Average Shot: 1 + CC x (CD - 1)."""
    assert average_multiplier(1.25, 3.0) == pytest.approx(1 + 1.25 * 2)


def test_vigilante_upgrades_only_crits() -> None:
    """Saved Critical_Hit: each Vigilante piece adds 5% to raise a crit's tier by one."""
    assert tiers(0.5, upgrade_chance=0.3) == pytest.approx({0: 0.5, 1: 0.35, 2: 0.15})


def test_noncrit_factor_only_on_non_crits() -> None:
    """Laetum Devouring Attrition (x21 at 50% on non-crits = x11 expected): gone from 100%."""
    assert crit.average_multiplier(0.5, 3.0, noncrit=11.0) == pytest.approx(0.5 * 11 + 0.5 * 3)
    assert crit.average_multiplier(1.0, 3.0, noncrit=11.0) == pytest.approx(3.0)
    assert crit.average_multiplier(1.5, 3.0, noncrit=11.0) == pytest.approx(4.0)


def test_crit_only_ratio() -> None:
    """30% crit at 3x: all hits average 1.6x, the crits 3x."""
    assert crit.crit_only_ratio(0.3, 3.0) == pytest.approx(3.0 / 1.6)
    assert crit.crit_only_ratio(1.2, 3.0) == pytest.approx(1.0)
    assert crit.crit_only_ratio(0.0, 3.0) == 1.0
