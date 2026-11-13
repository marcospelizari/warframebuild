"""Incarnon perks joined to guns by name (melee and unknown names drop out), plus the
Incarnon Form shot parts from reference/main_attack.json (`hits`: a part landing more than
once per shot is listed that many times)."""

from collections import defaultdict
from typing import Any

from app.gamedata.models import Incarnon, Perk, Weapon
from app.parse.incarnon import parse_perk
from app.pipeline.build.effects import Overrides
from app.pipeline.build.gaps import Gaps
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import DataGap, RefreshError
from app.pipeline.sources.wiki_incarnon import RawPerk

FILE = "main_attack.json"


def build(
    raw: list[RawPerk], guns: list[Weapon], overrides: Overrides, table: dict[str, Any], gaps: Gaps
) -> list[Incarnon]:
    """A gun with perks but no main_attack row is a gap (new gun: excluded, U7)."""
    by_name = {w.name.casefold(): w for w in guns}
    perks: dict[str, list[Perk]] = defaultdict(list)
    for r in raw:
        gun = by_name.get(r.weapon.casefold())
        if gun is None:
            continue
        parsed, form = parse_perk(r.lines, r.notes)
        text = r.lines + r.notes
        effects = overrides.apply(f"{gun.unique_name}#{r.name}", parsed, text)
        perks[gun.unique_name].append(
            Perk(tier=r.tier, name=r.name, form=form, text=text, effects=effects)
        )
    rows: dict[str, dict[str, Any]] = table.get("weapons", {})
    for uid in sorted(perks.keys() - rows.keys()):
        gun = next(w for w in guns if w.unique_name == uid)
        gaps.exclude(uid, gun.name, DataGap(f"Incarnon perks but no row in reference/{FILE}"))
        del perks[uid]
    _check(rows, {w.unique_name: w for w in guns}, set(perks) | gaps.ids)
    names = {w.unique_name: w.name for w in guns}
    return [
        Incarnon(
            unique_name=u,
            name=names[u],
            attacks=[
                part
                for part in rows[u]["incarnon"]
                for _ in range(rows[u].get("hits", {}).get(part, 1))
            ],
            no_multishot=rows[u].get("no_multishot", []),
            note=rows[u].get("note"),
            perks=p,
        )
        for u, p in sorted(perks.items())
    ]


def _check(rows: dict[str, dict[str, Any]], guns: dict[str, Weapon], known: set[str]) -> None:
    """Rows of guns with perks are valid; rows of excluded guns (in `known`) are kept."""
    stray = sorted(rows.keys() - known)
    if stray:
        raise RefreshError(f"reference/{FILE}: rows without perks {stray}")
    for uid, row in rows.items():
        if uid not in guns:
            continue  # excluded gun: its row is checked once it is built
        require_verified(row, FILE, uid)
        parts, flat = row.get("incarnon"), row.get("no_multishot", [])
        hits = row.get("hits", {})  # part -> hits per shot (Vectis embed, PLAN G75)
        known = {a.name for a in guns[uid].attacks}
        if not (
            isinstance(parts, list)
            and parts
            and all(isinstance(p, str) for p in parts)
            and len(set(parts)) == len(parts)
            and set(parts) <= known
            and isinstance(flat, list)
            and all(isinstance(p, str) for p in flat)
            and set(flat) <= set(parts)
            and isinstance(hits, dict)
            and set(hits) <= set(parts)
            and all(
                isinstance(n, int) and not isinstance(n, bool) and n >= 2 for n in hits.values()
            )
            and isinstance(row.get("source"), str)
            and isinstance(row.get("note"), str | None)
        ):
            raise RefreshError(f"reference/{FILE} {guns[uid].name}: invalid row {row}")
