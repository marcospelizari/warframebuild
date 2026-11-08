"""Gun mods: DE ExportUpgrades filtered by uniqueName rules (G11/G31), plus their sets."""

import json
from collections import Counter, defaultdict
from typing import Any

from pydantic import ValidationError

from app.data.build.common import RefreshError, clean_levels, clean_text, records
from app.data.models import Category, Mod, ModSet
from app.data.sources.de_export import MOD_CATEGORY


def build(
    upgrades: Any, mod_filter: dict[str, Any]
) -> tuple[list[Mod], list[ModSet], dict[str, int]]:
    rules = mod_filter["rules"]
    allow = {a["id"] for a in mod_filter.get("allow", [])}
    denied: Counter[str] = Counter()
    kept = []
    entries = records(upgrades, "ExportUpgrades")
    compat = _gun_compat(entries)
    for m in entries:
        category = _category(m, compat)
        if category is None:
            continue
        rule = None if m["uniqueName"] in allow else _deny_rule(m, rules)
        if rule:
            denied[rule] += 1
        elif not m.get("levelStats"):
            denied["no-level-stats"] += 1  # rivens (M2)
        else:
            kept.append(m | {"_category": category})

    names: defaultdict[str, list[str]] = defaultdict(list)
    for m in kept:
        names[m["name"]].append(m["uniqueName"])
    dups = {n: u for n, u in names.items() if len(u) > 1}
    if dups:
        raise RefreshError(
            "unclassified duplicate gun-mod names, add to "
            f"reference/mod_filter.json: {json.dumps(dups, indent=1)}"
        )

    try:
        mods = sorted((_mod(m) for m in kept), key=lambda m: m.unique_name)
    except ValidationError as error:
        raise RefreshError(f"invalid mod values: {error}") from error
    used_sets = {m.mod_set for m in mods if m.mod_set}
    sets_raw = {s["uniqueName"]: s for s in upgrades.get("ExportModSet", [])}
    missing = sorted(used_sets - sets_raw.keys())
    if missing:
        raise RefreshError(f"mod sets missing in ExportModSet: {missing}")
    sets = [
        ModSet(
            unique_name=uid,
            num_upgrades=sets_raw[uid]["numUpgradesInSet"],
            stats=[clean_text(s) for s in sets_raw[uid].get("stats", [])],
        )
        for uid in sorted(used_sets)
    ]
    return mods, sets, dict(sorted(denied.items()))


def _mod(m: dict[str, Any]) -> Mod:
    return Mod(
        unique_name=m["uniqueName"],
        name=m["name"],
        category=m["_category"],
        compat_name=m.get("compatName") or "",
        polarity=m["polarity"],
        rarity=m["rarity"],
        base_drain=m["baseDrain"],
        fusion_limit=m["fusionLimit"],
        is_utility=bool(m.get("isUtility", False)),
        mod_set=m.get("modSet"),
        description=clean_text("\n".join(m.get("description") or [])),
        level_stats=clean_levels(m["levelStats"]),
    )


def _gun_compat(entries: list[dict[str, Any]]) -> dict[str, Category]:
    """Compat names used by typed gun mods of exactly one category (Sniper -> primary)."""
    seen: defaultdict[str, set[Category]] = defaultdict(set)
    for m in entries:
        if m.get("type") in MOD_CATEGORY and m.get("compatName"):
            seen[m["compatName"]].add(MOD_CATEGORY[m["type"]])
    return {name: next(iter(cats)) for name, cats in seen.items() if len(cats) == 1}


def _category(m: dict[str, Any], compat: dict[str, Category]) -> Category | None:
    """DE `type`, or for an untyped mod (`---`: Sniper Ammo Mutation) its gun compat name."""
    if m.get("type") in MOD_CATEGORY:
        return MOD_CATEGORY[m["type"]]
    return compat.get(m.get("compatName") or "")


def _deny_rule(m: dict[str, Any], rules: list[dict[str, Any]]) -> str | None:
    for rule in rules:
        if rule["path_contains"] in m["uniqueName"]:
            prefix = rule.get("unless_name_starts")
            if prefix and m["name"].startswith(prefix):
                continue
            return str(rule["id"])
    return None
