"""`POST /api/calc`: the request and the scored build (G18). Fields are added, never renamed."""

from typing import Literal

from pydantic import Field

from app.api.schemas.base import ApiModel
from app.domain.effects import DamageType
from app.gamedata.builds import Forma
from app.gamedata.models import Category


class CalcRequest(ApiModel):
    weapon: str = Field(max_length=100, description="weapon slug")
    mods: list[str] = Field(
        default_factory=list, max_length=8, description="mod uniqueNames in slot order"
    )
    bonus_element: DamageType | None = None
    perks: list[str] = Field(default_factory=list, max_length=4, description="perk names")
    exilus: str | None = Field(None, max_length=200, description="exilus mod uniqueName")
    arcane: str | None = Field(None, max_length=200, description="arcane uniqueName")


class Source(ApiModel):
    kind: Literal["wiki", "reference", "de", "wfcd"]
    url: str


class Assumption(ApiModel):
    id: str
    text: str
    value: float | None = None
    source: Source | None = None


class WeaponRef(ApiModel):
    slug: str
    name: str
    category: Category
    weapon_type: str


class Slot(ApiModel):
    index: int
    mod: str | None  # uniqueName
    name: str | None
    rank: int | None
    polarity: str | None


class ArcaneRef(ApiModel):
    unique_name: str
    name: str


class BonusElement(ApiModel):
    damage_type: DamageType
    share: float


class Arsenal(ApiModel):
    damage: dict[DamageType, float]  # per projectile, not quantized (as in the arsenal)
    combined: dict[DamageType, list[DamageType]]  # combined element in `damage` -> its 2 parts
    total_damage: float
    critical_chance: float
    critical_multiplier: float
    status_chance: float
    multishot: float
    fire_rate: float
    magazine: float | None
    reload_time: float
    beam_ramp_start: float | None


class HeadDps(ApiModel):
    """Burst DPS when every direct hit lands on `head` (aiming, highest zoom)."""

    head: str  # e.g. "Grineer humanoid head"
    multiplier: float
    critical: bool  # critical-headshot flag
    zero_stacks: float  # headshot-triggered effects off
    # Hit-triggered effects (on headshot, on weak-point hit) at max stacks (ranked on, G70);
    # kill-triggered stacks are not counted yet.
    max_stacks: float
    triggered: list[str]  # entries with headshot-triggered effects
    source: Source


class Dps(ApiModel):
    direct_burst: float
    direct_sustained: float | None  # None when the modelled magazine cannot fire one shot
    head: HeadDps | None = None  # forms aimed at heads only
    # The Max objective (G80): DPS over 10 s on a neutral target, conditions held; the
    # reference head on forms aimed at heads. Equals a stored Max build's score (E8).
    max_score: float


class Headshot(ApiModel):
    reason: str
    source: Source | None  # None: a project decision, explained in `reason`


class EnemyFight(ApiModel):
    name: str
    unique_name: str  # key of a variant's `denominators`
    faction: str
    target: str  # body part hit: the head spot on forms aimed at heads, else "Body"
    ttk: float | None  # seconds; None = alive at the cap
    removed: float  # share of shield + health removed
    cost: float  # TTK, or cap / removed when alive (C3)


class FactionScore(ApiModel):
    faction: str
    score: float  # geometric mean cost of its enemies; lower is better


class Combat(ApiModel):
    level: int
    cap_s: float
    enemies: list[EnemyFight]
    factions: list[FactionScore]
    score: float  # geometric mean over the factions


class Build(ApiModel):
    dataset_hash: str
    weapon: WeaponRef
    form: Literal["normal", "incarnon"]
    perks: list[str]
    slots: list[Slot]
    exilus: Slot | None = None
    arcane: ArcaneRef | None = None
    bonus_element: BonusElement | None
    forma: Forma | None  # fewest-forma layout of these mods; None: none fits (Q6)
    arsenal: Arsenal
    dps: Dps
    headshot: Headshot | None  # this form is aimed at heads; None = body shots
    combat: Combat
    assumptions: list[Assumption]
