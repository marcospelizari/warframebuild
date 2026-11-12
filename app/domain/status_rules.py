"""Status numbers per damage type (gamedata `status_rules.json`, built from reference/).

The combat model wires each mechanic to fixed types; the numbers are data. A build's stack
cap bonuses ("+1 max Puncture stacks") apply through `with_extra_stacks`.
"""

from collections.abc import Mapping
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.debuffs import HeatStrip, Stacking
from app.domain.effects import DamageType
from app.domain.status import Detonation, Dot

# Debuffs the combat model counts by stacks.
STACKING = frozenset(
    {
        DamageType.PUNCTURE,
        DamageType.COLD,
        DamageType.CORROSIVE,
        DamageType.VIRAL,
        DamageType.MAGNETIC,
    }
)
# Types whose stack cap a build can raise: the stacking debuffs and Blast's detonation.
CAPPED = STACKING | {DamageType.BLAST}


class StatusRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    duration_s: Annotated[float, Field(gt=0)]  # one proc, x (1 + status duration)
    stacking: Stacking | None = None
    dot: Dot | None = None
    heat_strip: HeatStrip | None = None
    blast: Detonation | None = None


class StatusRules(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    types: dict[DamageType, StatusRule]

    @model_validator(mode="after")
    def _shape(self) -> "StatusRules":
        missing = sorted(set(DamageType) - self.types.keys())
        if missing:
            raise ValueError(f"no rule for {missing}")
        for t, rule in self.types.items():
            if (rule.stacking is not None) != (t in STACKING):
                raise ValueError(f"{t}: stacking only (and always) on {sorted(STACKING)}")
            if (rule.heat_strip is not None) != (t == DamageType.HEAT):
                raise ValueError(f"{t}: heat_strip only (and always) on heat")
            if (rule.blast is not None) != (t == DamageType.BLAST):
                raise ValueError(f"{t}: blast only (and always) on blast")
        if self.types[DamageType.HEAT].dot is None:
            raise ValueError("heat: dot required")
        return self

    def duration(self, t: DamageType) -> float:
        return self.types[t].duration_s

    def stacking(self, t: DamageType) -> Stacking:
        rule = self.types[t].stacking
        assert rule is not None  # validated
        return rule

    def dot(self, t: DamageType) -> Dot | None:
        return self.types[t].dot

    @property
    def heat_strip(self) -> HeatStrip:
        rule = self.types[DamageType.HEAT].heat_strip
        assert rule is not None  # validated
        return rule

    @property
    def blast(self) -> Detonation:
        rule = self.types[DamageType.BLAST].blast
        assert rule is not None  # validated
        return rule

    def with_extra_stacks(self, extra: Mapping[DamageType, int]) -> "StatusRules":
        """These rules with each type's stack cap raised by `extra` (never below 0)."""
        if not any(extra.values()):
            return self
        types = dict(self.types)
        for t, n in extra.items():
            rule = types[t]
            if rule.stacking is not None:
                types[t] = rule.model_copy(update={"stacking": rule.stacking.with_cap(n)})
            elif rule.blast is not None:
                cap = max(1, rule.blast.cap + n)
                types[t] = rule.model_copy(
                    update={"blast": rule.blast.model_copy(update={"cap": cap})}
                )
        return self.model_copy(update={"types": types})
