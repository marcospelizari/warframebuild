"""Data for guns export-plus does not list yet: reference/weapon_tags.json (tags, parent)."""

from typing import Any

from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError
from app.pipeline.sources.export_plus import ExportPlus, known

FILE = "weapon_tags.json"
KEYS = {"name", "tags", "parent", "source", "verified"}


def fill(data: dict[str, Any], plus: ExportPlus) -> tuple[dict[str, list[str]], dict[str, str]]:
    """export-plus tags and parents plus the reference rows; a row for a gun export-plus now
    lists fails."""
    tags, parents = dict(plus.weapon_tags), dict(plus.weapon_parents)
    for uid, row in data.get("weapons", {}).items():
        unknown = sorted(set(row) - KEYS)
        if unknown:
            raise RefreshError(f"reference/{FILE} {uid}: unknown keys {unknown}")
        require_verified(row, FILE, uid)
        if uid in plus.weapon_tags:
            raise RefreshError(f"reference/{FILE} {uid}: export-plus lists it now; remove the row")
        value = row.get("tags")
        if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
            raise RefreshError(f"reference/{FILE} {uid}: `tags` must be a list of strings")
        parent = row.get("parent")
        if not isinstance(parent, str):
            raise RefreshError(f"reference/{FILE} {uid}: `parent` (class path) is required")
        tags[uid] = known(sorted(value), f"reference/{FILE} {uid}")
        parents[uid] = parent
    return tags, parents


def check_known(data: dict[str, Any], gun_ids: set[str]) -> None:
    unknown = sorted(set(data.get("weapons", {})) - gun_ids)
    if unknown:
        raise RefreshError(f"reference/{FILE}: unknown guns {unknown}")
