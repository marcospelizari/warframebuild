"""Incarnon perks joined to guns by name (melee and unknown names drop out), plus the
Incarnon Form shot parts from reference/main_attack.json."""

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
        perks[gun.unique_name].append(Perk(tier=r.tier, name=r.name, form=form, effects=effects))
    attacks = _attacks(table, {w.unique_name: w for w in guns}, set(perks))
    names = {w.unique_name: w.name for w in guns}
    return [
        Incarnon(unique_name=u, name=names[u], attacks=attacks[u], perks=p)
        for u, p in sorted(perks.items())
    ]


def _attacks(
    table: dict[str, Any], guns: dict[str, Weapon], incarnon: set[str]
) -> dict[str, list[str]]:
    rows: dict[str, dict[str, Any]] = table.get("weapons", {})
    missing = sorted(guns[u].name for u in incarnon - rows.keys())
    stray = sorted(rows.keys() - incarnon)
    if missing or stray:
        raise RefreshError(f"reference/{FILE}: no row for {missing}; rows without perks {stray}")
    out = {}
    for uid, row in rows.items():
        require_verified(row, FILE, uid)
        parts = row.get("incarnon")
        known = {a.name for a in guns[uid].attacks}
        if not parts or not isinstance(parts, list) or not set(parts) <= known:
            raise RefreshError(f"reference/{FILE} {guns[uid].name}: unknown attacks {parts}")
        out[uid] = [str(p) for p in parts]
    return out
