"""reference/aura_buffs.json -> the gun auras (G91), pinned to DE's text: a row whose aura
is gone or whose DE text changed is left out and listed for re-check."""

from typing import Any

from pydantic import ValidationError

from app.domain.auras import Aura, Auras
from app.pipeline.build.inputs import require_cites, require_verified
from app.pipeline.errors import RefreshError

FILE = "aura_buffs.json"
KEYS = {"name", "de_text", "weapon_types", "source", "verified"}
CHANGES = {"effect", "armor_kept", "shield_kept"}


def build(
    table: dict[str, Any],
    upgrades: list[dict[str, Any]],
    weapon_types: set[str],
    titles: dict[str, str],
) -> tuple[Auras, list[str]]:
    """The auras, and the names of rows left out because DE's aura changed."""
    rows = table.get("auras")
    if not isinstance(rows, dict):
        raise RefreshError(f"reference/{FILE}: needs `auras` (DE uniqueName -> row)")
    de = {u["uniqueName"]: u for u in upgrades}
    out, changed = [], []
    for uid, row in rows.items():
        if not isinstance(row, dict) or not KEYS <= set(row) <= KEYS | CHANGES:
            raise RefreshError(f"reference/{FILE} {uid}: keys {sorted(KEYS)} + one of {CHANGES}")
        require_verified(row, FILE, uid)
        require_cites(row["source"], FILE, uid, titles)
        listed = row["weapon_types"]
        if listed is not None and not set(listed) & weapon_types:
            raise RefreshError(f"reference/{FILE} {row['name']}: no gun has a type in {listed}")
        if _de_text(de.get(uid)) != row["de_text"]:
            changed.append(row["name"])
            continue
        fields = {k: v for k, v in row.items() if k not in {"de_text", "verified"}}
        try:
            out.append(Aura(unique_name=uid, **fields))
        except (ValidationError, TypeError) as error:
            raise RefreshError(f"reference/{FILE} {row['name']}: {error}") from error
    return Auras(auras=sorted(out, key=lambda a: a.name)), sorted(changed)


def _de_text(entry: dict[str, Any] | None) -> str | None:
    """DE's max-rank stat text, lines joined; None when the aura is gone."""
    levels = (entry or {}).get("levelStats") or []
    return " ".join(levels[-1].get("stats", [])) if levels else None
