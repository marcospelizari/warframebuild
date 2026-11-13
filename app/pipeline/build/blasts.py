"""reference/blasts.json: the AoE attack of each gun's primary fire (PLAN G49 P2), for the
primer score's radius and the enemies around the target. Alt-fire blasts never count.
`blast` null: the primary fire has none. A gun with a normal-form AoE attack and no row
primes one enemy and is listed for review."""

from typing import Any

from app.gamedata.models import Incarnon, Weapon
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError

FILE = "blasts.json"
KEYS = {"name", "blast", "source", "verified"}
AOE = "AoE"


def apply(
    table: dict[str, Any], guns: list[Weapon], incarnon: list[Incarnon], excluded: set[str]
) -> tuple[list[Weapon], list[str]]:
    """Guns with their blast, and the names of guns that need a row."""
    rows: dict[str, Any] = table.get("weapons", {})
    by_id = {w.unique_name: w for w in guns}
    stray = sorted(rows.keys() - by_id.keys() - excluded)
    if stray:
        raise RefreshError(f"reference/{FILE}: unknown guns {stray}")
    form_parts = {i.unique_name: set(i.attacks) for i in incarnon}
    out, missing = [], []
    for w in guns:
        blasts = {
            a.name
            for a in w.attacks
            if a.shot_type == AOE
            and a.falloff is not None
            and a.falloff.end
            and a.name not in form_parts.get(w.unique_name, set())
        }
        row = rows.get(w.unique_name)
        if row is None:
            if blasts:
                missing.append(w.name)
            out.append(w)
            continue
        _check(w, row, blasts)
        out.append(w.model_copy(update={"blast": row["blast"]}) if row["blast"] else w)
    return out, missing


def _check(w: Weapon, row: dict[str, Any], blasts: set[str]) -> None:
    require_verified(row, FILE, w.unique_name)
    if set(row) != KEYS or not isinstance(row["source"], str):
        raise RefreshError(f"reference/{FILE} {w.name}: keys must be {sorted(KEYS)}")
    if row["blast"] is not None and row["blast"] not in blasts:
        raise RefreshError(
            f"reference/{FILE} {w.name}: {row['blast']!r} is not one of its normal-form AoE "
            f"attacks with a radius {sorted(blasts)}"
        )
