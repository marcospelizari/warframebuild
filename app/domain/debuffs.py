"""Status debuffs on the target by active stacks (saved <Type>_Damage pages, Status_Effect).

Stack counts are expected values in the combat model: below one stack a debuff scales
linearly from nothing to its first-stack value.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Stacking:
    first: float  # value at one stack
    step: float  # added per further stack
    cap: int  # stacks counted
    duration_s: float  # base duration of each stack

    def value(self, stacks: float) -> float:
        n = min(max(stacks, 0.0), self.cap)
        return n * self.first if n < 1 else self.first + self.step * (n - 1)


# Armor removed (Corrosive_Damage:21; 10 stacks, each its own 8 s).
CORROSIVE = Stacking(first=0.26, step=0.06, cap=10, duration_s=8.0)
# Extra damage to health / shields: x2 at one stack, +0.25 per stack (Viral_Damage:20, :25;
# Magnetic_Damage:23, :28).
VIRAL = Stacking(first=1.0, step=0.25, cap=10, duration_s=6.0)
MAGNETIC = Stacking(first=1.0, step=0.25, cap=10, duration_s=6.0)
# Flat crit chance on direct hits, not AoE (Puncture_Damage:18-20).
PUNCTURE = Stacking(first=0.05, step=0.05, cap=5, duration_s=10.0)
# Flat crit damage after mods, direct hits only (Cold_Damage:18-20, Critical_Hit:208-213);
# +0.5 from the 9th stack. The 10-stack freeze (+1.0 for 3 s) is not modelled.
COLD = Stacking(first=0.1, step=0.05, cap=9, duration_s=6.0)

# Heat strip: 15%, 30%, 40%, 50% at 0.5, 1, 1.5, 2 s after the first proc, steps slowed by
# status duration (Heat_Damage:79, :85). Armor returning after the burn ends is not
# modelled: the weapon keeps firing.
HEAT_STEPS = (0.15, 0.30, 0.40, 0.50)
HEAT_STEP_S = 0.5


def heat_strip(seconds_burning: float, duration_bonus: float) -> float:
    step = int(max(seconds_burning, 0.0) // (HEAT_STEP_S * (1 + duration_bonus)))
    return HEAT_STEPS[min(step, len(HEAT_STEPS)) - 1] if step else 0.0


def armor_kept(corrosive_stacks: float, heat: float) -> float:
    """Strips multiply (Corrosive_Damage:31-42)."""
    return (1 - CORROSIVE.value(corrosive_stacks)) * (1 - heat)
