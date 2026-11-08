"""Condition Overload-style "Direct Damage" bonus (Galvanized Aptitude/Savvy/Shot), saved
Condition_Overload_(Mechanic): Mechanics, Application Behaviors, Math.

The bonus is `value x stacks x status types on the target` and joins the damage in one of
three ways per attack: `adding` (with the Serration group: `(damage bonuses x other
multipliers) + bonus`), `multiplying` (a separate factor) or `none` (AoE parts, some
attacks). The page's catalog lists only discrepant attacks and says anything not listed is
adding, so `adding` is the default even for projectiles (which the page says "tend to"
multiply). Which one an attack uses is data (weapons.json,
reference/galvanized_behaviour.json).
"""

from enum import StrEnum


class DirectBonus(StrEnum):
    ADDING = "adding"
    MULTIPLYING = "multiplying"
    NONE = "none"


def bonus(value: float, stacks: int, status_types: int) -> float:
    """+40% per status type at 2 stacks with 2 types on the target -> 1.6."""
    if stacks < 0 or status_types < 0:
        raise ValueError("stacks and status types are counts")
    return value * stacks * status_types


def damage_factor(behaviour: DirectBonus, damage_multiplier: float, direct: float) -> float:
    """Factor on the base damage once the direct bonus applies; `damage_multiplier` is the
    hit's own (Serration group x separate damage factors)."""
    if behaviour == DirectBonus.ADDING:
        return damage_multiplier + direct
    if behaviour == DirectBonus.MULTIPLYING:
        return damage_multiplier * (1 + direct)
    return damage_multiplier
