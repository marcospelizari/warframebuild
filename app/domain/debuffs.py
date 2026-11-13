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
    After the burn ends the steps return in reverse, one per `restore_s`, then none
    (Heat_Damage:81; the source gives no status-duration effect on the return)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    steps: Annotated[tuple[float, ...], Field(min_length=1)]
    step_s: Annotated[float, Field(gt=0)]
    restore_s: Annotated[float, Field(gt=0)]

    def strip(self, seconds_burning: float, duration_bonus: float) -> float:
        step = int(max(seconds_burning, 0.0) // (self.step_s * (1 + duration_bonus)))
        return self.steps[min(step, len(self.steps)) - 1] if step else 0.0

    def after_burn(self, stripped: float, seconds_since_end: float) -> float:
        """Strip left `seconds_since_end` after a burn that ended at `stripped`."""
        if stripped not in self.steps:
            return 0.0
        left = self.steps.index(stripped) - int(max(seconds_since_end, 0.0) // self.restore_s)
        return self.steps[left] if left >= 0 else 0.0


def armor_kept(corrosive: Stacking, corrosive_stacks: float, heat: float) -> float:
    """Strips multiply (Corrosive_Damage:31-42)."""
    return (1 - corrosive.value(corrosive_stacks)) * (1 - heat)
