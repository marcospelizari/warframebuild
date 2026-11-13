"""reference/status_rules.json -> status numbers per damage type (durations, stacking
debuffs, DoT, Heat strip, Blast), each row citing its saved wiki page and line."""

from typing import Any

from pydantic import ValidationError

from app.domain.effects import DamageType
from app.domain.status_rules import StatusRule, StatusRules
from app.pipeline.build.inputs import require_cites, require_verified
from app.pipeline.errors import RefreshError

FILE = "status_rules.json"
_NOT_RULE = {"source", "verified"}


def build(table: dict[str, Any], titles: dict[str, str]) -> StatusRules:
    """`titles`: saved wiki stem -> title (reference/wiki_pages.json)."""
    rows = table.get("types")
    if not isinstance(rows, dict):
        raise RefreshError(f"reference/{FILE}: needs `types` (damage type -> row)")
    types: dict[DamageType, StatusRule] = {}
    for key, row in rows.items():
        if key not in DamageType.__members__.values() or not isinstance(row, dict):
            raise RefreshError(f"reference/{FILE}: unknown damage type {key!r}")
        require_verified(row, FILE, key)
        require_cites(row.get("source"), FILE, key, titles)
        try:
            types[DamageType(key)] = StatusRule(
                **{k: v for k, v in row.items() if k not in _NOT_RULE}
            )
        except (ValidationError, TypeError) as error:
            raise RefreshError(f"reference/{FILE} {key}: {error}") from error
    try:
        return StatusRules(types=types)
    except ValidationError as error:
        raise RefreshError(f"reference/{FILE}: {error}") from error
