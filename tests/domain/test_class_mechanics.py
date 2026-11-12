import pytest

from app.domain.class_mechanics import (
    beam_level,
    beam_ramp,
    sniper_combo_multiplier,
)


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


def test_beam_level_ramps_up_and_decays_after_a_stop() -> None:
    """Continuous_Weapon:19: 0.6 s to full; 0.8 s after it stops hitting, back to the start
    value over 2 s."""
    assert beam_level(0.2, 0.2, 0.3) == pytest.approx(0.6)
    assert beam_level(0.2, 0.2, 1.0) == 1.0
    assert beam_level(0.2, 1.0, 0.0, off_target=0.8) == 1.0  # still inside the delay
    assert beam_level(0.2, 1.0, 0.0, off_target=1.8) == pytest.approx(0.6)  # half decayed
    assert beam_level(0.2, 1.0, 0.0, off_target=5.0) == pytest.approx(0.2)
