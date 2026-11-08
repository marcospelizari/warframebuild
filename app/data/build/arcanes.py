"""Arcanes: DE ExportRelicArcane entries with level stats; compatibility comes in step 3."""

from typing import Any

from app.data.build.common import clean_levels
from app.data.models import Arcane

ARCANE_PREFIX = "/Lotus/Upgrades/CosmeticEnhancers/"


def build(entries: list[dict[str, Any]]) -> list[Arcane]:
    return sorted(
        (
            Arcane(
                unique_name=a["uniqueName"],
                name=a["name"],
                rarity=a.get("rarity"),
                level_stats=clean_levels(a["levelStats"]),
            )
            for a in entries
            if a["uniqueName"].startswith(ARCANE_PREFIX) and a.get("levelStats")
        ),
        key=lambda a: a.unique_name,
    )
