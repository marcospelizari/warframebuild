"""Mod families (V4): mods that cannot be equipped together on one gun.

Derived from DE data, corrected by hand-checked entries in reference/mod_families.json:
- DE marks variants by uniqueName suffix: `...ModExpert` (Primed), `...SPMod`
  (Galvanized) share the base mod's stem (`WeaponFireIterationsMod`: Split Chamber,
  Galvanized Chamber, and the pistol/shotgun equivalents, which never meet on one gun);
- a name starting with Primed / Amalgam / Spectral that ends with another mod's full
  name is a variant of it (Primed Bane of Grineer, Amalgam Argonak Metal Auger,
  Spectral Serration; in-game rule checked by Marcos 2026-11-08). Other shared
  endings are not variants (Augur Seeker / Seeker, Sweeping Serration / Serration);
- `join` entries merge families the data does not link, `split` entries take a mod out.
"""

import re
from typing import Any

from app.data.build.common import RefreshError, require_verified

_VARIANT = re.compile(r"(?:Expert|SP)(?=Mod$)|(?<=Mod)Expert$")
_NAME_PREFIXES = ("Primed ", "Amalgam ", "Spectral ")


def stem(unique_name: str) -> str:
    return _VARIANT.sub("", unique_name.rsplit("/", 1)[-1])


def derive(mods: list[dict[str, Any]], corrections: dict[str, Any]) -> dict[str, str]:
    """uniqueName -> family id, only for mods that share a family with another mod.

    `mods` are raw entries with `uniqueName` and `name`. The id is the smallest stem
    in the family, so it stays stable while members are added.
    """
    ids = {m["uniqueName"] for m in mods}
    parent = {uid: uid for uid in ids}

    def find(uid: str) -> str:
        while parent[uid] != uid:
            parent[uid] = parent[parent[uid]]
            uid = parent[uid]
        return uid

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    by_stem: dict[str, str] = {}
    by_name: dict[str, str] = {m["name"]: m["uniqueName"] for m in mods}
    names = {m["uniqueName"]: m["name"] for m in mods}
    for m in mods:
        uid = m["uniqueName"]
        first = by_stem.setdefault(stem(uid), uid)
        if first != uid:
            union(uid, first)
        if m["name"].startswith(_NAME_PREFIXES):
            words = m["name"].split(" ")
            # Longest other mod name the variant ends with: "Amalgam Argonak Metal Auger"
            # -> "Metal Auger".
            for i in range(1, len(words)):
                base = by_name.get(" ".join(words[i:]))
                if base:
                    union(uid, base)
                    break

    split = set()
    for entry in corrections.get("split", []):
        _known(entry["mods"], ids, entry)
        split.update(entry["mods"])
    for entry in corrections.get("join", []):
        _known(entry["mods"], ids, entry)
        for uid in entry["mods"][1:]:
            union(uid, entry["mods"][0])

    groups: dict[str, list[str]] = {}
    for uid in sorted(ids - split):
        groups.setdefault(find(uid), []).append(uid)
    out: dict[str, str] = {}
    for members in groups.values():
        if len(members) > 1:
            # Prefer the stem of base mods (no Primed/Amalgam name), then the commonest.
            base_mods = [u for u in members if not names[u].startswith(_NAME_PREFIXES)] or members
            stems = [stem(uid) for uid in base_mods]
            family = min(stems, key=lambda s: (-stems.count(s), s))
            out |= dict.fromkeys(members, family)
    return out


def _known(uids: list[str], ids: set[str], entry: dict[str, Any]) -> None:
    require_verified(entry, "mod_families.json", str(entry.get("id")))
    missing = [u for u in uids if u not in ids]
    if missing:
        raise RefreshError(
            f"reference/mod_families.json {entry.get('id')}: unknown gun mods {missing}"
        )
