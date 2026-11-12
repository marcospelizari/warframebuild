"""Request and response models of the JSON API (G18-G21). Fields are added, never renamed."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.effects import DamageType, Support
from app.gamedata.builds import Forma
from app.gamedata.models import Category


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiError(ApiModel):
    code: str
    message: str
    field: str | None = None


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


class StoredBuild(ApiModel):
    """A precomputed build: its search outcome and the build scored as /calc scores it."""

    status: Literal["optimal", "best_found", "what_if"]
    search_scope: list[str]  # C6
    evaluations: int
    score: float  # Max: dps.max_score; others: 1 / the objective's combat cost
    forma: Forma | None  # None: no layout fits (flagged, Q6)
    without: dict[str, float]  # F8: score with that mod, exilus or arcane removed
    build: Build


class VariantBuilds(ApiModel):
    element: DamageType | None  # progenitor bonus; None: the gun has none
    max: StoredBuild
    recommended: StoredBuild
    factions: dict[str, StoredBuild]
    denominators: dict[str, float]  # per enemy uniqueName: its faction build's cost (G35)


class ElementChoice(ApiModel):
    element: DamageType
    rank: int  # 1 = best Recommended search
    searched: float  # Recommended score of the full search with this element (G85)
    what_if: float  # element 1's Recommended mods with this element (G15)
    optimized: bool  # only optimized elements are selectable (C7)


class BuildsResponse(ApiModel):
    release: str  # release id; also the ETag
    dataset_hash: str
    weapon: WeaponRef
    elements: list[ElementChoice]  # empty without a progenitor bonus
    variants: list[VariantBuilds]  # element 1 first


class WeaponItem(ApiModel):
    slug: str
    name: str
    category: Category
    weapon_type: str
    incarnon: bool
    progenitor: bool  # Kuva/Tenet/Coda bonus element
    mastery: int  # mastery rank needed
    image: str | None  # /img URL; None when the icon is not cached


class ExcludedWeapon(ApiModel):
    name: str
    reason: str


class WeaponList(ApiModel):
    dataset_hash: str
    weapons: list[WeaponItem]
    # Guns the tool does not build, with why (G19); filtered by `q` only (no category stored).
    excluded: list[ExcludedWeapon]


class ModItem(ApiModel):
    unique_name: str
    name: str
    polarity: str
    rarity: str
    rank: int  # max rank (builds use max rank, Q33)
    drain: int  # at max rank, before polarity
    exilus: bool  # fits the exilus slot
    family: str | None  # mods sharing a family clash (V4)
    mod_set: str | None
    support: Support  # R6: how fully its effects are modelled
    stats: list[str]  # max-rank text
    description: str
    image: str | None  # /img URL; None when the picture is not cached
    compatible: bool
    reason: str | None  # why it does not fit this gun


class ArcaneItem(ApiModel):
    unique_name: str
    name: str
    rarity: str | None
    support: Support
    stats: list[str]  # max-rank text
    image: str | None  # /img URL; None when the picture is not cached
    compatible: bool
    reason: str | None


class PerkItem(ApiModel):
    name: str
    form: Literal["both", "normal", "incarnon"]
    support: Support


class PerkTier(ApiModel):
    tier: int
    options: list[PerkItem]  # one may be chosen per tier


class ModList(ApiModel):
    """Everything the editor's picker offers for one gun (F7, G20)."""

    dataset_hash: str
    weapon: WeaponRef
    mods: list[ModItem]  # every mod of the gun's category
    arcanes: list[ArcaneItem]  # every arcane of the gun's category
    perks: list[PerkTier]  # empty for guns without Incarnon perks
