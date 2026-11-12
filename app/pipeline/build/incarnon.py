"""Incarnon perks joined to guns by name (melee and unknown names drop out), plus the
Incarnon Form shot parts from reference/main_attack.json (`hits`: a part landing more than
once per shot is listed that many times)."""

from collections import defaultdict
from typing import Any

from app.gamedata.models import Incarnon, Perk, Weapon
from app.parse.incarnon import parse_perk
from app.pipeline.build.effects import Overrides
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError
from app.pipeline.sources.wiki_incarnon import RawPerk

FILE = "main_attack.json"


def build(
    raw: list[RawPerk], guns: list[Weapon], overrides: Overrides, table: dict[str, Any]
) -> list[Incarnon]:
    by_name = {w.name.casefold(): w for w in guns}
    perks: dict[str, list[Perk]] = defaultdict(list)
    for r in raw:
        gun = by_name.get(r.weapon.casefold())
        if gun is None:
            continue
        parsed, form = parse_perk(r.lines, r.notes)
        effects = overrides.apply(f"{gun.unique_name}#{r.name}", parsed)
        perks[gun.unique_name].append(
            Perk(tier=r.tier, name=r.name, form=form, text=r.lines, effects=effects)
        )
    rows = _rows(table, {w.unique_name: w for w in guns}, set(perks))
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


def _rows(
    table: dict[str, Any], guns: dict[str, Weapon], incarnon: set[str]
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = table.get("weapons", {})
    missing = sorted(guns[u].name for u in incarnon - rows.keys())
    stray = sorted(rows.keys() - incarnon)
    if missing or stray:
        raise RefreshError(f"reference/{FILE}: no row for {missing}; rows without perks {stray}")
    for uid, row in rows.items():
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
    return rows
