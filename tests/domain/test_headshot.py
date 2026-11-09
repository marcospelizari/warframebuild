import pytest

from app.domain.headshot import Head, factor

GRINEER = Head(3.0, critical=True)


def test_weak_point_bonus_on_a_head() -> None:
    """Saved Enemy_Body_Parts, Weak Point Hits: (3 + 1.5 x (3.5 + 0.75)) = 9.375x."""
    assert factor(GRINEER, 3.5 + 0.75, 0.0) == pytest.approx(9.375)


def test_headshot_bonuses_multiply() -> None:
    """Same page, Headshots: x (1 + 0.3 + 0.4) with Primary Deadhead and Prowl = 15.9375x."""
    assert factor(GRINEER, 3.5 + 0.75, 0.3 + 0.4) == pytest.approx(15.9375)


def test_headshot_bonuses_add_up() -> None:
    """Same page, Notes: Daikyu with Primary Deadhead and Amalgam Target Acquired:
    3 x (1 + 0.3 + 0.75)."""
    assert factor(GRINEER, 0.0, 0.3 + 0.75) == pytest.approx(3 * 2.05)


def test_flat_head_keeps_only_headshot_bonuses() -> None:
    """Same page, Notes: 1x heads ignore Acuity-like bonuses, keep Deadhead-like ones."""
    assert factor(GRINEER, 3.5, 0.3, flat=True) == pytest.approx(1.3)


def test_extra_headshot_factor_multiplies() -> None:
    """Same page, Notes: Cernos Prime's 50% headshot bonus is multiplicative."""
    assert factor(GRINEER, 0.0, 0.0, extra=0.5) == pytest.approx(4.5)
