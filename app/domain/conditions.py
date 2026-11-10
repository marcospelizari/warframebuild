"""When conditional effects count and at how many stacks (PLAN R2, G78).

A fight starts mid-mission, in steady state: kill stacks at max, hit-triggered buffs at the
stacks the build's own trigger rate holds. "When the buff times out, one stack is lost and
the buff duration resets" (saved Primary_Merciless:36, Galvanized_Aptitude:45): triggers
arriving faster than the duration never lose a stack, slower ones hold a share of one.
Stacks "removed all at once" when they time out give the same expected value (saved
Arcane_Enhancement:1392, 1452, 1731; Cascadia_Flare:55; Split_Flights:61-62). Incarnon
perks: the rule is assumed.
"""

from app.domain.effects import Operation, Trigger

# Triggers a fight never produces: no melee, no abilities (checklist, step 4).
NEVER = frozenset({Trigger.ON_ABILITY_CAST, Trigger.ON_MELEE_KILL})
KILL = frozenset({Trigger.ON_KILL, Trigger.ON_HEADSHOT_KILL, Trigger.ON_WEAK_POINT_KILL})
HEAD_KILL = frozenset({Trigger.ON_HEADSHOT_KILL, Trigger.ON_WEAK_POINT_KILL})
HEAD_HIT = frozenset({Trigger.ON_HEADSHOT, Trigger.ON_WEAK_POINT_HIT})


def steady_stacks(
    triggers_per_s: float, duration_s: float | None, max_stacks: int, chance: float = 1.0
) -> float:
    """Expected stacks held: max when grants arrive at least once per duration (or the buff
    has none), else the share of time one stack is up."""
    grants = triggers_per_s * chance
    if grants <= 0:
        return 0.0
    if duration_s is None:
        return float(max_stacks)
    held = grants * duration_s
    return float(max_stacks) if held >= 1 else held


def reload_uptime(duration_s: float | None, cycle_s: float | None) -> float:
    """Share of time a buff granted by each reload is up; `cycle_s` = reload to reload."""
    if cycle_s is None or cycle_s <= 0:
        return 0.0
    return 1.0 if duration_s is None else min(1.0, duration_s / cycle_s)


def first_shot_share(shots_per_magazine: float | None) -> float:
    """Share of shots that are the first of their magazine."""
    if shots_per_magazine is None or shots_per_magazine <= 0:
        return 0.0
    return min(1.0, 1 / shots_per_magazine)


def value_at(value: float, operation: Operation, stacks: float) -> float:
    """One stack's value at `stacks` expected stacks; a separate factor moves from x1."""
    if operation == Operation.MULTIPLY:
        return 1 + (value - 1) * stacks
    return value * stacks
