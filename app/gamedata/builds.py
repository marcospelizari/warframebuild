"""Schema of a release's precomputed builds, one file per gun (PLAN G15, G35, C4, C6)."""

from typing import Literal

from pydantic import Field

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


class Variant(Model):
    element: DamageType | None  # progenitor bonus; None: the gun has none
    max: Build
    recommended: Build
    factions: dict[str, Build]
    denominators: dict[str, float]  # per enemy: its faction build's cost (G35)


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
