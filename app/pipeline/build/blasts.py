"""The blast(s) of each gun's primary fire (PLAN G49): the primer score's radius and the
enemies around the target. From the saved wiki weapon modules: the AoE attacks whose
`AttackParentIndex` is the scored attack (WFCD's first, paired with DE's numbers), or that
attack itself when it is AoE. Alt-fire blasts hang off their own attack, so they never count.
reference/blasts.json holds the exceptions, each with its reason: `blasts` replaces the
derived list; `shot` (optional) names the primary-fire attacks the primer fires when DE's
numbers are another mode (Epitaph: the uncharged shot). Listed for review, with no row: a gun
with an AoE attack that the modules do not list (it primes one enemy), and one whose module
has an AoE attack with no parent link besides the scored attack (it keeps the derived list)."""

from typing import Any

from app.gamedata.models import Attack, Incarnon, Weapon
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError

FILE = "blasts.json"
KEYS = {"name", "blasts", "reason", "source", "verified"}
OPTIONAL = {"shot"}
AOE = "AoE"


def apply(
    table: dict[str, Any], guns: list[Weapon], incarnon: list[Incarnon], excluded: set[str]
) -> tuple[list[Weapon], list[str]]:
    """Guns with their blasts and primer shot, and the names of guns to review."""
    rows: dict[str, Any] = table.get("weapons", {})
    by_id = {w.unique_name: w for w in guns}
    stray = sorted(rows.keys() - by_id.keys() - excluded)
    if stray:
        raise RefreshError(f"reference/{FILE}: unknown guns {stray}")
    form_parts = {i.unique_name: set(i.attacks) for i in incarnon}
    out, missing = [], []
    for w in guns:
        own = [a for a in w.attacks if a.name not in form_parts.get(w.unique_name, set())]
        row = rows.get(w.unique_name)
        if row is not None:
            _check(w, row, {a.name for a in own if _blast(a)}, {a.name for a in own})
            update = {"blasts": row["blasts"], "primer_shot": row.get("shot", [])}
        elif own and any(_blast(a) for a in own) and own[0].forced_procs is None:
            missing.append(w.name)  # not in the saved modules: no parent links
            update = {"blasts": []}
        else:
            if unlinked(own):
                missing.append(w.name)  # the module does not say which attack it belongs to
            update = {"blasts": derived(own)}
        out.append(w.model_copy(update=update))
    return out, missing


def derived(own: list[Attack]) -> list[str]:
    """The scored attack's blasts by the module's parent links."""
    if not own:
        return []
    scored = own[0]
    kids = [a.name for a in own if _blast(a) and a.parent == scored.name]
    return ([scored.name] if _blast(scored) else []) + kids


def unlinked(own: list[Attack]) -> list[str]:
    """AoE attacks, other than the scored one, that the module parents to no attack."""
    return [a.name for a in own[1:] if _blast(a) and a.parent is None]


def _blast(a: Attack) -> bool:
    return a.shot_type == AOE and a.falloff is not None and bool(a.falloff.end)


def _check(w: Weapon, row: dict[str, Any], blasts: set[str], own: set[str]) -> None:
    require_verified(row, FILE, w.unique_name)
    if not KEYS <= set(row) <= KEYS | OPTIONAL or not all(
        isinstance(row[k], str) for k in ("reason", "source")
    ):
        raise RefreshError(
            f"reference/{FILE} {w.name}: keys must be {sorted(KEYS)}, optional {sorted(OPTIONAL)}"
        )
    chosen, shot = row["blasts"], row.get("shot", [])
    if not (_names(chosen) and set(chosen) <= blasts):
        raise RefreshError(
            f"reference/{FILE} {w.name}: `blasts` must name its normal-form AoE attacks "
            f"with a radius {sorted(blasts)}"
        )
    if not (_names(shot) and set(shot) <= own and set(chosen) <= set(shot or chosen)):
        raise RefreshError(
            f"reference/{FILE} {w.name}: `shot` must list its own normal-form attacks, "
            f"the blasts among them"
        )


def _names(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(n, str) for n in value)
        and len(set(value)) == len(value)
    )
