"""Status debuffs on the target by active stacks (saved <Type>_Damage pages, Status_Effect).

Stack counts are expected values in the combat model: below one stack a debuff scales
linearly from nothing to its first-stack value. The numbers come from gamedata
(`StatusRules`).
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Stacking(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    first: float  # value at one stack
    step: float  # added per further stack
    cap: Annotated[int, Field(ge=1)]  # stacks counted

    def value(self, stacks: float) -> float:
        n = min(max(stacks, 0.0), self.cap)
        return n * self.first if n < 1 else self.first + self.step * (n - 1)

    def with_cap(self, extra: int) -> "Stacking":
        return self.model_copy(update={"cap": max(0, self.cap + extra)})


class HeatStrip(BaseModel):
    """Armor stripped at each step after the first proc; steps slowed by status duration.
    Armor returning after the burn ends is not modelled: the weapon keeps firing."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    steps: Annotated[tuple[float, ...], Field(min_length=1)]
    step_s: Annotated[float, Field(gt=0)]

    def strip(self, seconds_burning: float, duration_bonus: float) -> float:
        step = int(max(seconds_burning, 0.0) // (self.step_s * (1 + duration_bonus)))
        return self.steps[min(step, len(self.steps)) - 1] if step else 0.0


def armor_kept(corrosive: Stacking, corrosive_stacks: float, heat: float) -> float:
    """Strips multiply (Corrosive_Damage:31-42)."""
    return (1 - corrosive.value(corrosive_stacks)) * (1 - heat)
