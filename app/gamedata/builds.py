"""Schema of a release's precomputed builds, one file per gun (PLAN G15, G35, C4, C6)."""

from typing import Literal

from pydantic import Field

from app.domain.archon_shards import Shard
from app.domain.effects import DamageType
from app.domain.polarity import Polarity
from app.gamedata.models import Model


class FormaSlot(Model):
    polarity: Polarity | None
    forma: bool
    drain: int


class Forma(Model):
    regular: list[FormaSlot]
    exilus: FormaSlot | None
    forma: int
    used: int
    capacity: int


class ShardStep(Model):
    shard: Shard
    score: float  # the build's score with this shard and the ones before it


class ShardAdvice(Model):
    """Shards beside a build, slot by slot (G91, optimize.shards): each next slot takes the
    shard that gains most on top of the earlier ones; stops when no shard gains."""

    normal: list[ShardStep]
    tauforged: list[ShardStep]
    conditions: list[str]  # what buffs counted at their cap need (Topaz)


class AuraGain(Model):
    aura: str  # DE uniqueName
    score: float  # the build's score with this aura


class Build(Model):
    mods: list[str]  # uniqueNames, slot order
    exilus: str | None
    arcane: str | None  # uniqueName
    perks: list[str]  # names, one per chosen EVO tier
    score: float  # Max: burst DPS; others: 1 / combat cost
    status: Literal["optimal", "best_found", "what_if"]
    search_scope: list[str]  # C6
    evaluations: int
    forma: Forma | None  # None: no layout fits (flagged, Q6)
    costs: dict[str, float]  # combat cost per scored enemy uniqueName; empty for Max
    # F8: score with that mod, exilus or arcane (uniqueName) removed, the rest re-scored
    # (no new search); empty in releases made before it.
    without: dict[str, float] = Field(default_factory=dict)
    shards: ShardAdvice | None = None  # None in releases made before G91
    # Every aura that fits the gun, best first (G91, optimize.auras); None: before G91.
    auras: list[AuraGain] | None = None


class PrimerNumbers(Model):
    """What the Primer build's burst does to follow-up hits (G49, optimize.primer)."""

    boost: float  # follow-up damage multiplier on the target
    area_boost: float  # the same on an enemy around it (1 without a blast)
    enemies: float  # enemies primed, the target included
    radius: float | None  # m, the blast after radius mods; None: no blast
    status_types: float  # different status types kept up on the target


class Variant(Model):
    element: DamageType | None  # progenitor bonus; None: the gun has none
    max: Build
    recommended: Build
    factions: dict[str, Build]
    denominators: dict[str, float]  # per enemy: its faction build's cost (G35)
    primer: Build | None = None  # G49; None in releases made before it
    primer_numbers: PrimerNumbers | None = None


class ElementRow(Model):
    element: DamageType
    rank: int  # 1 = best Recommended search
    searched: float  # Recommended score of the full search with this element (G85)
    what_if: float  # element 1's Recommended mods with this element (G15)
    optimized: bool


class WeaponBuilds(Model):
    weapon: str  # uniqueName
    slug: str
    variants: list[Variant]  # element 1 first
    elements: list[ElementRow]  # empty without a progenitor bonus
