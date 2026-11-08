import pytest

from app.domain.class_mechanics import beam_ramp, beam_ramp_average, sniper_combo_multiplier


@pytest.mark.parametrize(
    "combo,expected", [(0, 1.0), (1, 1.0), (2, 1.5), (5, 1.5), (6, 2.0), (17, 2.0), (18, 2.5)]
)
def test_sniper_combo(combo: int, expected: float) -> None:
    """Saved Sniper_Rifle: 1.5 + 0.5 x floor(log3(combo / minimum)), minimum 2 (Lanka)."""
    assert sniper_combo_multiplier(combo, 2) == expected


def test_beam_ramp() -> None:
    """Saved Continuous_Weapon: 20% start, 100% after 0.6 s (linear assumed)."""
    assert beam_ramp(0.2, 0) == 0.2
    assert beam_ramp(0.2, 0.3) == pytest.approx(0.6)
    assert beam_ramp(0.2, 5) == 1.0
    assert beam_ramp_average(0.2, 0.6) == pytest.approx(0.6)
    assert beam_ramp_average(0.2, 1.2) == pytest.approx((0.6 * 0.6 + 0.6) / 1.2)
