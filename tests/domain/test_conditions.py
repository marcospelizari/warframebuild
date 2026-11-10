import pytest

from app.domain.conditions import first_shot_share, reload_uptime, steady_stacks, value_at
from app.domain.effects import Operation


def test_stacks_hold_at_max_when_triggers_outpace_the_timeout() -> None:
    """Primary_Merciless:36: a timeout drops one stack and resets the duration, so a trigger
    at least once per duration never loses one."""
    assert steady_stacks(0.25, 4.0, 12) == 12
    assert steady_stacks(3.0, 12.0, 40) == 40


def test_slower_triggers_hold_a_share_of_one_stack() -> None:
    assert steady_stacks(0.1, 4.0, 12) == pytest.approx(0.4)
    assert steady_stacks(0.0, 4.0, 12) == 0
    assert steady_stacks(1.0, 4.0, 12, chance=0.1) == pytest.approx(0.4)


def test_buff_without_duration_stays_at_max() -> None:
    assert steady_stacks(0.01, None, 3) == 3


def test_reload_buff_uptime() -> None:
    """+fire rate for 9 s after a reload, reloading every 12 s: up 75% of the time."""
    assert reload_uptime(9.0, 12.0) == pytest.approx(0.75)
    assert reload_uptime(9.0, 4.0) == 1
    assert reload_uptime(9.0, None) == 0  # the gun never reloads


def test_first_shot_share() -> None:
    assert first_shot_share(5) == pytest.approx(0.2)
    assert first_shot_share(1) == 1
    assert first_shot_share(None) == 0


def test_value_at_stacks() -> None:
    assert value_at(0.3, Operation.STACKING_MULTIPLY, 12) == pytest.approx(3.6)
    # Primed Chamber x2 on one shot in five = x1.2 on average.
    assert value_at(2.0, Operation.MULTIPLY, 0.2) == pytest.approx(1.2)
