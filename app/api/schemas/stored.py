"""`GET /api/weapons/{slug}/builds`: a gun's precomputed builds (Q28b); fields are only added."""

from typing import Literal

from app.api.schemas.base import ApiModel
from app.api.schemas.build import Build, WeaponRef
from app.domain.effects import DamageType
from app.gamedata.builds import Forma


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
