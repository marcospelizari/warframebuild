import pytest

from app.domain.effects import Effect, Operation, Stat
from app.domain.stats import modded, modded_time, value_for


def bonus(stat: Stat, value: float, op: Operation = Operation.STACKING_MULTIPLY) -> Effect:
    return Effect(stat=stat, value=value, operation=op)


def pairs(*effects: Effect) -> list[tuple[Effect, float]]:
    return [(e, e.value) for e in effects]


def test_additive_bonuses_sum() -> None:
    """Saved Calculating_Bonuses: Speed Trigger +60% and Shred +30% give +90% fire rate."""
    fire = pairs(bonus(Stat.FIRE_RATE, 0.6), bonus(Stat.FIRE_RATE, 0.3))
    assert modded(10, Stat.FIRE_RATE, fire) == pytest.approx(19)


def test_order_of_operations() -> None:
    """Same page: base x (1 + additive) x separate factors + flat."""
    effects = pairs(
        bonus(Stat.CRITICAL_CHANCE, 1.5),
        bonus(Stat.CRITICAL_CHANCE, 1.2, Operation.MULTIPLY),
        bonus(Stat.CRITICAL_CHANCE, 0.3, Operation.ADD),
        bonus(Stat.DAMAGE, 9.0),  # other stat: ignored
    )
    assert modded(0.2, Stat.CRITICAL_CHANCE, effects) == pytest.approx(0.2 * 2.5 * 1.2 + 0.3)


def test_lock_keeps_the_base() -> None:
    effects = pairs(bonus(Stat.MULTISHOT, 0.9), bonus(Stat.MULTISHOT, 0, Operation.LOCK))
    assert modded(1, Stat.MULTISHOT, effects) == 1


def test_never_below_zero() -> None:
    assert modded(1, Stat.FIRE_RATE, pairs(bonus(Stat.FIRE_RATE, -1.5))) == 0


def test_class_value_and_stacks() -> None:
    e = Effect(stat=Stat.DAMAGE, value=0.3, max_stacks=12, class_values={"Bow": 0.6})
    assert value_for(e, "Rifle", 12) == pytest.approx(3.6)
    assert value_for(e, "Bow", 1) == 0.6
    with pytest.raises(ValueError):
        value_for(e, "Rifle", 13)


def test_modded_time() -> None:
    """Saved Calculation, Modded Stats: time / (1 + speed bonus)."""
    assert modded_time(2.0, 1.0) == 1.0
