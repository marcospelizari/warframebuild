"""Gun arcanes: DE ExportRelicArcane stats, slot (primary/secondary, class limit) from WFCD."""

from typing import Any

from pydantic import ValidationError

from app.data.build.common import RefreshError, clean_levels
from app.data.build.effects import Overrides
from app.data.models import Arcane
from app.data.sources.wfcd import GUN_ARCANE_TYPES, OTHER_ARCANE_TYPES

ARCANE_PREFIX = "/Lotus/Upgrades/CosmeticEnhancers/"


def build(
    de_entries: list[dict[str, Any]], wfcd_arcanes: list[dict[str, Any]], overrides: Overrides
) -> list[Arcane]:
    """Every DE arcane must be typed by WFCD: one WFCD has not listed yet fails the
    refresh instead of silently missing from the optimizer."""
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
            "GUN_ARCANE_TYPES or OTHER_ARCANE_TYPES in app/data/sources/wfcd.py"
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
    untyped = sorted(de.keys() - seen)
    if untyped:
        raise RefreshError(
            f"DE arcanes not in WFCD Arcanes.json yet (slot unknown): {untyped}; "
            "wait for WFCD or rerun later"
        )
    try:
        return [_arcane(de[uid], slots[uid], overrides) for uid in sorted(slots)]
    except ValidationError as error:
        raise RefreshError(f"invalid arcane values: {error}") from error


def _arcane(a: dict[str, Any], kind: str, overrides: Overrides) -> Arcane:
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
    )
