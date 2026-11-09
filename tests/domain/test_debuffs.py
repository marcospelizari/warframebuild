import pytest

from app.domain import debuffs


def test_status_stacks_per_the_pages() -> None:
    assert debuffs.CORROSIVE.value(1) == pytest.approx(0.26)
    assert debuffs.CORROSIVE.value(10) == pytest.approx(0.80)
    assert debuffs.CORROSIVE.value(25) == pytest.approx(0.80)
    assert debuffs.CORROSIVE.value(0.5) == pytest.approx(0.13)
    assert 1 + debuffs.VIRAL.value(10) == pytest.approx(4.25)  # +325%
    assert debuffs.PUNCTURE.value(5) == pytest.approx(0.25)
    assert debuffs.COLD.value(9) == pytest.approx(0.5)
    assert debuffs.COLD.value(10) == pytest.approx(0.5)  # freeze not modelled


def test_heat_strip_steps_and_strips_multiply() -> None:
    """Heat_Damage:79, :85: 15%, 30%, 40%, 50% at 0.5, 1, 1.5, 2 s after the first proc."""
    assert debuffs.heat_strip(0.2, 0) == 0.0
    assert debuffs.heat_strip(0.5, 0) == 0.15
    assert debuffs.heat_strip(1.2, 0) == 0.30
    assert debuffs.heat_strip(1.9, 0) == 0.40
    assert debuffs.heat_strip(2.0, 0) == 0.50
    assert debuffs.heat_strip(5, 0) == 0.50
    assert debuffs.heat_strip(0.7, 1.0) == 0.0  # steps every 1 s with +100% duration
    assert debuffs.heat_strip(3.9, 1.0) == 0.40  # full strip only at 4 s
    assert debuffs.armor_kept(10, 0.5) == pytest.approx(0.2 * 0.5)
