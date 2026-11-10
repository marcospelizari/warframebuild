"""Mod classes each gun accepts (G82): export-plus parent chains + reference/weapon_classes.json."""

from typing import Any

from app.gamedata.models import Weapon
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError

FILE = "weapon_classes.json"


def apply(data: dict[str, Any], guns: list[Weapon], parents: dict[str, str]) -> list[Weapon]:
    """Each gun's `mod_classes`: itself, its parent chain, the classes of the chain's root,
    of its category and of every weapon. A root without a row fails the refresh."""
    entries = [("all", data.get("all"))]
    entries += [(f"category.{c}", r) for c, r in data.get("category", {}).items()]
    entries += [(f"roots.{u}", r) for u, r in data.get("roots", {}).items()]
    for key, row in entries:
        if not isinstance(row, dict) or not _paths(row.get("classes")):
            raise RefreshError(f"reference/{FILE} {key}: `classes` must be a list of paths")
        require_verified(row, FILE, key)
    out = []
    for gun in guns:
        chain = [gun.unique_name]
        while (parent := parents.get(chain[-1])) is not None and parent not in chain:
            chain.append(parent)
        root = data["roots"].get(chain[-1])
        category = data["category"].get(gun.category.value)
        if root is None or category is None:
            raise RefreshError(f"{gun.name}: class root {chain[-1]} has no row in reference/{FILE}")
        classes = {*chain, *root["classes"], *category["classes"], *data["all"]["classes"]}
        out.append(gun.model_copy(update={"mod_classes": sorted(classes)}))
    return out


def _paths(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)
