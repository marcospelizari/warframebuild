"""Effect model: what one mod, arcane or set bonus does to a gun (Q8/R2, R6).

Values are fractions (+165% -> 1.65) except `multiply` factors (x1.55 -> 1.55)
and counts. How effects combine is the damage domain's job (step 4); this module
only describes them.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DamageType(StrEnum):
    """Damage types. Source encodings (DE slots, tags) live in the data adapters."""

    IMPACT = "impact"
    PUNCTURE = "puncture"
    SLASH = "slash"
    HEAT = "heat"
    COLD = "cold"
    ELECTRICITY = "electricity"
    TOXIN = "toxin"
    BLAST = "blast"
    RADIATION = "radiation"
    GAS = "gas"
    MAGNETIC = "magnetic"
    VIRAL = "viral"
    CORROSIVE = "corrosive"
    VOID = "void"
    TAU = "tau"


class Stat(StrEnum):
    DAMAGE = "damage"  # base damage (Serration)
    ELEMENT = "element"  # +X% of base as elemental `damage_type` (Hellfire)
    PHYSICAL = "physical"  # +X% to the base's own Impact/Puncture/Slash only (Bore);
    # no effect when the gun has none of that type (saved Calculating_Bonuses)
    FACTION_DAMAGE = "faction_damage"  # vs `faction` (Bane, Expel)
    MULTISHOT = "multishot"
    FIRE_RATE = "fire_rate"
    CRITICAL_CHANCE = "critical_chance"
    CRITICAL_DAMAGE = "critical_damage"
    STATUS_CHANCE = "status_chance"
    STATUS_DURATION = "status_duration"
    STATUS_DAMAGE = "status_damage"  # Elementalist
    DIRECT_DAMAGE = "direct_damage"  # Galvanized: per status type on the target
    WEAK_POINT_DAMAGE = "weak_point_damage"
    WEAK_POINT_CRITICAL_CHANCE = "weak_point_critical_chance"
    HEADSHOT_MULTIPLIER = "headshot_multiplier"
    MAGAZINE_CAPACITY = "magazine_capacity"
    RELOAD_SPEED = "reload_speed"
    AMMO_EFFICIENCY = "ammo_efficiency"
    FORCED_PROC = "forced_proc"  # chance to add a `damage_type` proc (V8)
    CRIT_TIER_UPGRADE = "crit_tier_upgrade"  # Vigilante set: chance to enhance a crit
    STATUS_STACK_CAP = "status_stack_cap"  # +N max stacks of `damage_type`'s status


PHYSICAL_TYPES = frozenset({DamageType.IMPACT, DamageType.PUNCTURE, DamageType.SLASH})


class Faction(StrEnum):
    """Faction names as mod text writes them (Bane/Expel/Cleanse "Damage to X").

    Mapping to the enemy factions (factions.json, R4) is step 8's job; a name not
    listed here leaves the line unparsed, so a new faction never passes as full.
    """

    CORPUS = "corpus"
    GRINEER = "grineer"
    INFESTED = "infested"
    OROKIN = "orokin"  # Corrupted
    MURMUR = "murmur"


class Operation(StrEnum):
    STACKING_MULTIPLY = "stacking_multiply"  # additive % within the stat's group
    MULTIPLY = "multiply"  # separate factor
    ADD = "add"  # flat, after % bonuses
    LOCK = "lock"  # "cannot be modified": the stat keeps its base value
    BASE = "base"  # added to the base value before % bonuses (Incarnon "Increase Base X")


class Trigger(StrEnum):
    ALWAYS = "always"
    ON_HIT = "on_hit"
    ON_CRIT = "on_crit"
    ON_NONCRIT = "on_noncrit"
    ON_NONCRIT_NO_STATUS = "on_noncrit_no_status"  # neither crit nor status proc
    ON_KILL = "on_kill"
    ON_HEADSHOT = "on_headshot"
    ON_HEADSHOT_KILL = "on_headshot_kill"
    ON_WEAK_POINT_HIT = "on_weak_point_hit"
    ON_WEAK_POINT_KILL = "on_weak_point_kill"
    ON_STATUS = "on_status"  # `trigger_damage_type` = that status only
    ON_RELOAD = "on_reload"
    ON_ABILITY_CAST = "on_ability_cast"
    ON_MELEE_KILL = "on_melee_kill"
    FIRST_SHOT = "first_shot"  # first shot in the magazine


# Forced procs the combat timeline models; any other trigger would be dropped there.
_PROC_TRIGGERS = frozenset({Trigger.ALWAYS, Trigger.ON_CRIT, Trigger.ON_STATUS})


class Support(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"


class FireRateBoost(BaseModel):
    """`factor` x value while the modded fire rate is below `below` (Internal Bleeding:
    "x2 when Fire Rate is below 2.5"; exactly 2.5 gets no boost, saved Internal_Bleeding)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    below: Annotated[float, Field(gt=0)]
    factor: Annotated[float, Field(gt=0)]


class Effect(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    stat: Stat
    value: float  # sign kept: -15% Damage -> -0.15
    operation: Operation = Operation.STACKING_MULTIPLY
    damage_type: DamageType | None = None
    faction: Faction | None = None
    trigger: Trigger = Trigger.ALWAYS
    trigger_damage_type: DamageType | None = None
    while_aiming: bool = False
    duration_s: Annotated[float, Field(gt=0)] | None = None
    max_stacks: Annotated[int, Field(ge=1)] = 1
    chance: Annotated[float, Field(gt=0, le=1)] = 1.0  # chance the trigger grants it
    # Value per WFCD weapon_type where it differs ("x2 for Bows" -> {"Bow": 2 * value}).
    class_values: dict[str, float] = Field(default_factory=dict)
    fire_rate_boost: FireRateBoost | None = None
    # Value counts once per status type on the target (Galvanized: "+40% Direct Damage per
    # Status Type affecting the target").
    per_status_type: bool = False

    @model_validator(mode="after")
    def _shape(self) -> "Effect":
        needs_type = self.stat in (
            Stat.ELEMENT,
            Stat.PHYSICAL,
            Stat.FORCED_PROC,
            Stat.STATUS_STACK_CAP,
        )
        if needs_type != (self.damage_type is not None):
            raise ValueError(f"{self.stat}: damage_type {'required' if needs_type else 'unused'}")
        if self.stat == Stat.PHYSICAL and self.damage_type not in PHYSICAL_TYPES:
            raise ValueError("physical: damage_type must be impact, puncture or slash")
        if self.stat == Stat.ELEMENT and self.damage_type in PHYSICAL_TYPES:
            raise ValueError("element: physical types use stat physical")
        if (self.stat == Stat.FACTION_DAMAGE) != (self.faction is not None):
            raise ValueError("faction only (and always) on faction_damage")
        if (self.trigger_damage_type is not None) and self.trigger != Trigger.ON_STATUS:
            raise ValueError("trigger_damage_type only on on_status")
        if self.stat == Stat.FORCED_PROC and self.trigger not in _PROC_TRIGGERS:
            raise ValueError("forced_proc: trigger must be always, on_crit or on_status")
        if self.stat == Stat.STATUS_STACK_CAP and self.operation != Operation.ADD:
            raise ValueError("status_stack_cap: operation must be add")
        if self.fire_rate_boost is not None and self.stat != Stat.FORCED_PROC:
            raise ValueError("fire_rate_boost only on forced_proc")
        if self.per_status_type and self.stat != Stat.DIRECT_DAMAGE:
            raise ValueError("per_status_type only on direct_damage")
        return self


class Parsed(BaseModel):
    """Parser result for one entry: effects, plus the damage-related text it could not model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effects: list[Effect] = Field(default_factory=list)
    unparsed: list[str] = Field(default_factory=list)  # damage-related lines not modelled
    requires_trigger: str | None = None  # DE trigger the mod is limited to (SEMI)

    @property
    def support(self) -> Support:
        if not self.unparsed:
            return Support.FULL
        return Support.PARTIAL if self.effects else Support.UNSUPPORTED
