import pytest

from app.domain.debuffs import armor_kept
from app.domain.effects import DamageType as D
from app.domain.status_rules import StatusRules


def test_status_stacks_per_the_pages(rules: StatusRules) -> None:
    corrosive = rules.stacking(D.CORROSIVE)
    assert corrosive.value(1) == pytest.approx(0.26)
    assert corrosive.value(10) == pytest.approx(0.80)
    assert corrosive.value(25) == pytest.approx(0.80)
    assert corrosive.value(0.5) == pytest.approx(0.13)
    assert 1 + rules.stacking(D.VIRAL).value(10) == pytest.approx(4.25)  # +325%
    assert rules.stacking(D.PUNCTURE).value(5) == pytest.approx(0.25)
    assert rules.stacking(D.COLD).value(9) == pytest.approx(0.5)
    assert rules.stacking(D.COLD).value(10) == pytest.approx(0.5)  # freeze not modelled


def test_heat_strip_steps_and_strips_multiply(rules: StatusRules) -> None:
    """Heat_Damage:79, :85: 15%, 30%, 40%, 50% at 0.5, 1, 1.5, 2 s after the first proc."""
    heat = rules.heat_strip
    assert heat.strip(0.2, 0) == 0.0
    assert heat.strip(0.5, 0) == 0.15
    assert heat.strip(1.2, 0) == 0.30
    assert heat.strip(1.9, 0) == 0.40
    assert heat.strip(2.0, 0) == 0.50
    assert heat.strip(5, 0) == 0.50
    assert heat.strip(0.7, 1.0) == 0.0  # steps every 1 s with +100% duration
    assert heat.strip(3.9, 1.0) == 0.40  # full strip only at 4 s
    assert armor_kept(rules.stacking(D.CORROSIVE), 10, 0.5) == pytest.approx(0.2 * 0.5)


def test_cap_bonus_counts_one_more_stack(rules: StatusRules) -> None:
    puncture = rules.with_extra_stacks({D.PUNCTURE: 1}).stacking(D.PUNCTURE)
    assert puncture.cap == 6
    assert puncture.value(6) == pytest.approx(0.30)
    assert rules.stacking(D.PUNCTURE).cap == 5  # the shared rules are unchanged
