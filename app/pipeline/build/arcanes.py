"""Gun arcanes: DE ExportRelicArcane stats, slot (primary/secondary, class limit) from WFCD."""

from typing import Any

from pydantic import ValidationError

from app.gamedata.models import Arcane
from app.pipeline.build.effects import Overrides
from app.pipeline.build.gaps import Gaps
from app.pipeline.errors import DataGap, RefreshError
from app.pipeline.sources.de_text import clean_levels
from app.pipeline.sources.wfcd import GUN_ARCANE_TYPES, OTHER_ARCANE_TYPES

ARCANE_PREFIX = "/Lotus/Upgrades/CosmeticEnhancers/"


def build(
    de_entries: list[dict[str, Any]],
    wfcd_arcanes: list[dict[str, Any]],
    overrides: Overrides,
    textures: dict[str, str | None],
    gaps: Gaps,
) -> list[Arcane]:
    """Every DE arcane must be typed by WFCD: a new one WFCD has not listed yet is left out
    with its reason in `gaps` (U8), never silently missing from the optimizer."""
    slots: dict[str, str] = {}
    seen: set[str] = set()
    unknown = set()
    duplicates = set()
    for a in wfcd_arcanes:
        uid, kind = a["uniqueName"], a.get("type")
        if uid in seen:
            duplicates.add(uid)
        seen.add(uid)
        if kind in GUN_ARCANE_TYPES:
            slots[uid] = kind
        elif kind not in OTHER_ARCANE_TYPES:
            unknown.add(kind)
    if unknown:
        raise RefreshError(
            f"unknown WFCD arcane types {sorted(map(str, unknown))}: add them to "
            "GUN_ARCANE_TYPES or OTHER_ARCANE_TYPES in app/pipeline/sources/wfcd.py"
        )
    if duplicates:
        raise RefreshError(f"arcanes listed twice in WFCD Arcanes.json: {sorted(duplicates)}")
    de = {
        a["uniqueName"]: a
        for a in de_entries
        if a.get("levelStats") and a["uniqueName"].startswith(ARCANE_PREFIX)
    }
    missing = sorted(slots.keys() - de.keys())
    if missing:
        raise RefreshError(f"gun arcanes in WFCD without DE level stats: {missing}")
    for uid in sorted(de.keys() - seen):  # slot unknown until WFCD lists it (U8)
        gaps.exclude(uid, de[uid]["name"], DataGap("in the game files, not in WFCD's data yet"))
    try:
        return [_arcane(de[uid], slots[uid], overrides, textures.get(uid)) for uid in sorted(slots)]
    except ValidationError as error:
        raise RefreshError(f"invalid arcane values: {error}") from error


def _arcane(a: dict[str, Any], kind: str, overrides: Overrides, texture: str | None) -> Arcane:
    category, weapon_type = GUN_ARCANE_TYPES[kind]
    levels = clean_levels(a["levelStats"])
    return Arcane(
        unique_name=a["uniqueName"],
        name=a["name"],
        category=category,
        weapon_type=weapon_type,
        rarity=a.get("rarity"),
        level_stats=levels,
        effects=overrides.effects(a["uniqueName"], levels[-1]),
        texture_location=texture,
    )
