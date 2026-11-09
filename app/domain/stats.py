"""One modded stat from its bonuses (saved Calculating_Bonuses, Order of Operations).

`Resultant = Base x (1 + sum of additive bonuses) x product of separate factors + flat`.
Callers pass only the effects that are active for the case they evaluate (conditions,
stacks and uptime are the caller's job, R2); each effect's value is already resolved
for the weapon class (`value_for`) and its stack count.
"""

import math
from collections.abc import Sequence

from app.domain.effects import Effect, Operation, Stat


def value_for(effect: Effect, weapon_type: str, stacks: int = 1) -> float:
    """The effect's value on this weapon class ("x2 for Bows") at `stacks` stacks."""
    if not 1 <= stacks <= effect.max_stacks:
        raise ValueError(f"{effect.stat}: {stacks} stacks, max {effect.max_stacks}")
    return effect.class_values.get(weapon_type, effect.value) * stacks


def modded(base: float, stat: Stat, bonuses: Sequence[tuple[Effect, float]]) -> float:
    """`bonuses`: (effect, resolved value) pairs; only those for `stat` count.

    A `lock` effect keeps the base value ("cannot be modified", e.g. Acuity multishot).
    The result never goes below 0.
    """
    base += math.fsum(v for e, v in bonuses if e.stat == stat and e.operation == Operation.BASE)
    additive: list[float] = []
    factor = 1.0
    flat: list[float] = []
    for effect, value in bonuses:
        if effect.stat != stat:
            continue
        if effect.operation == Operation.LOCK:
            return base
        if effect.operation == Operation.STACKING_MULTIPLY:
            additive.append(value)
        elif effect.operation == Operation.BASE:
            continue
        elif effect.operation == Operation.MULTIPLY:
            factor *= value
        else:
            flat.append(value)
    return max(0.0, base * (1 + math.fsum(additive)) * factor + math.fsum(flat))


def modded_time(base: float, speed_bonus: float) -> float:
    """Reload and charge time: `base / (1 + speed bonuses)` (saved Calculation, Modded Stats)."""
    if speed_bonus <= -1:
        raise ValueError("speed bonus at or below -100% gives no finite time")
    return base / (1 + speed_bonus)
