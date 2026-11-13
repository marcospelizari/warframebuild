"""reference/blasts.json: the AoE attack of each gun's primary fire (PLAN G49 P2), for the
primer score's radius and the enemies around the target. Alt-fire blasts never count.
`blast` null: the primary fire has none. `shot` (optional): the primary-fire attacks the
primer fires when DE's summary is another mode (Epitaph's uncharged shot, not the charged
one); the blast is one of them. A gun with a normal-form AoE attack and no row primes one
enemy and is listed for review."""

from typing import Any

from app.gamedata.models import Incarnon, Weapon
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError

FILE = "blasts.json"
KEYS = {"name", "blast", "source", "verified"}
OPTIONAL = {"shot"}
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
        own = {a.name for a in w.attacks} - form_parts.get(w.unique_name, set())
        _check(w, row, blasts, own)
        out.append(w.model_copy(update={"blast": row["blast"], "primer_shot": row.get("shot", [])}))
    return out, missing


def _check(w: Weapon, row: dict[str, Any], blasts: set[str], own: set[str]) -> None:
    require_verified(row, FILE, w.unique_name)
    if not KEYS <= set(row) <= KEYS | OPTIONAL or not isinstance(row["source"], str):
        raise RefreshError(
            f"reference/{FILE} {w.name}: keys must be {sorted(KEYS)}, optional {sorted(OPTIONAL)}"
        )
    shot = row.get("shot", [])
    if not (
        isinstance(shot, list)
        and all(isinstance(n, str) for n in shot)
        and len(set(shot)) == len(shot)
        and set(shot) <= own
        and (not shot or row["blast"] is None or row["blast"] in shot)
    ):
        raise RefreshError(
            f"reference/{FILE} {w.name}: `shot` must list its own normal-form attacks, "
            f"the blast among them"
        )
    if row["blast"] is not None and row["blast"] not in blasts:
        raise RefreshError(
            f"reference/{FILE} {w.name}: {row['blast']!r} is not one of its normal-form AoE "
            f"attacks with a radius {sorted(blasts)}"
        )
