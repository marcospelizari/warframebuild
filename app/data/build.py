"""Raw sources -> validated gamedata models. Pure: reads files, returns models, writes nothing."""

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.data.models import (
    DAMAGE_TYPES,
    UNVERIFIED_DAMAGE_SLOTS,
    Arcane,
    Attack,
    Exclusion,
    Falloff,
    Join,
    Mod,
    ModSet,
    Weapon,
)
from app.data.sources import load_json

GUN_CATEGORIES = {"LongGuns": "primary", "Pistols": "secondary"}
GUN_MOD_TYPES = ("PRIMARY", "SECONDARY")
ARCANE_PREFIX = "/Lotus/Upgrades/CosmeticEnhancers/"
_TAG = re.compile(r"<[A-Z0-9_]+>")
_SLUG = re.compile(r"[^a-z0-9]+")


class RefreshError(RuntimeError):
    pass


@dataclass(frozen=True)
class Dataset:
    weapons: list[Weapon]
    excluded_weapons: list[Exclusion]
    mods: list[Mod]
    mod_sets: list[ModSet]
    denied_mods: dict[str, int]
    arcanes: list[Arcane]
    joins: list[Join]
    game_update: str | None


def clean_text(text: str) -> str:
    """Strip DE markup (`<DT_SLASH_COLOR>` …); untrusted text, kept as plain text only."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("<LINE_SEPARATOR>", "\n")
    return _TAG.sub("", text).strip()


def slugify(name: str) -> str:
    return _SLUG.sub("-", name.lower()).strip("-")


def build(raw_dir: Path, reference_dir: Path) -> Dataset:
    de_weapons = _records(load_json(raw_dir / "de/ExportWeapons_en.json"), "ExportWeapons")
    upgrades = load_json(raw_dir / "de/ExportUpgrades_en.json")
    arcanes_raw = _records(load_json(raw_dir / "de/ExportRelicArcane_en.json"), "ExportRelicArcane")
    manifest = _records(load_json(raw_dir / "de/ExportManifest.json"), "Manifest")
    wfcd = [
        *_list(load_json(raw_dir / "wfcd/Primary.json")),
        *_list(load_json(raw_dir / "wfcd/Secondary.json")),
    ]
    fire_overrides = _reference(reference_dir / "fire_overrides.json")["weapons"]
    mod_filter = _reference(reference_dir / "mod_filter.json")

    weapons, excluded, joins = _weapons(de_weapons, wfcd, manifest, fire_overrides)
    mods, sets, denied = _mods(upgrades, mod_filter)
    arcanes = sorted(
        (
            Arcane(
                unique_name=a["uniqueName"],
                name=a["name"],
                rarity=a.get("rarity"),
                level_stats=[[clean_text(s) for s in lvl["stats"]] for lvl in a["levelStats"]],
            )
            for a in arcanes_raw
            if a["uniqueName"].startswith(ARCANE_PREFIX) and a.get("levelStats")
        ),
        key=lambda a: a.unique_name,
    )
    if not weapons or not mods or not arcanes:
        raise RefreshError(
            f"empty dataset: {len(weapons)} weapons, {len(mods)} mods, {len(arcanes)} arcanes"
        )
    return Dataset(weapons, excluded, mods, sets, denied, arcanes, joins, _game_update(wfcd))


def _weapons(
    de_weapons: list[dict[str, Any]],
    wfcd: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
    fire_overrides: dict[str, dict[str, Any]],
) -> tuple[list[Weapon], list[Exclusion], list[Join]]:
    de = {w["uniqueName"]: w for w in de_weapons}
    textures = {m["uniqueName"]: m.get("textureLocation") for m in manifest}
    by_id: dict[str, dict[str, Any]] = {}
    for w in wfcd:
        if w["uniqueName"] in by_id:
            raise RefreshError(f"duplicate WFCD entry: {w['uniqueName']}")
        by_id[w["uniqueName"]] = w
    unmatched = sorted(u for u in by_id if u not in de)
    if unmatched:
        raise RefreshError(f"WFCD guns missing in DE ExportWeapons: {unmatched}")
    de_guns = {
        u for u, w in de.items() if w.get("productCategory") in GUN_CATEGORIES and w.get("trigger")
    }
    missing = sorted(de_guns - by_id.keys())
    if missing:
        raise RefreshError(f"DE guns missing in WFCD: {[de[u]['name'] for u in missing]}")

    kept: list[tuple[dict[str, Any], dict[str, Any]]] = []
    excluded: list[Exclusion] = []
    for uid in sorted(by_id):
        d, w = de[uid], by_id[uid]
        reason = None
        if d["productCategory"] not in GUN_CATEGORIES:
            reason = f"not a primary or secondary gun (DE category {d['productCategory']})"
        elif uid in fire_overrides and "exclude" in fire_overrides[uid]:
            reason = str(fire_overrides[uid]["exclude"])
        elif not d.get("fireRate") or d["fireRate"] <= 0:
            raise RefreshError(
                f"{d['name']} ({uid}): no usable fire rate; add it to reference/fire_overrides.json"
            )
        if reason:
            excluded.append(Exclusion(unique_name=uid, name=d["name"], reason=reason))
        else:
            kept.append((d, w))

    slugs = _slugs([(d["uniqueName"], d["name"]) for d, _ in kept])
    weapons = [
        _weapon(d, w, slugs[d["uniqueName"]], textures.get(d["uniqueName"])) for d, w in kept
    ]
    joins = [
        Join(unique_name=d["uniqueName"], de_name=d["name"], wfcd_name=w["name"]) for d, w in kept
    ]
    return weapons, excluded, joins


def _weapon(d: dict[str, Any], w: dict[str, Any], slug: str, texture: str | None) -> Weapon:
    uid = d["uniqueName"]
    per_shot = d["damagePerShot"]
    if len(per_shot) != 20:
        raise RefreshError(f"{d['name']}: damagePerShot has {len(per_shot)} entries, expected 20")
    if any(per_shot[i] for i in UNVERIFIED_DAMAGE_SLOTS):
        raise RefreshError(f"{d['name']}: damage in an unmapped damagePerShot slot")
    damage = {t: float(v) for t, v in zip(DAMAGE_TYPES, per_shot, strict=False) if v}
    # WFCD lists each attack (charged, per pellet, AoE part); DE gives one summary, so
    # values legitimately differ. The main attack is chosen later (main_attack.json).
    attacks = [_attack(a, d["name"]) for a in w.get("attacks") or []]
    category = GUN_CATEGORIES[d["productCategory"]]
    if w.get("category", "").lower() != category:
        raise RefreshError(f"{d['name']}: DE says {category}, WFCD says {w.get('category')}")
    return Weapon(
        unique_name=uid,
        slug=slug,
        name=d["name"],
        category=category,  # type: ignore[arg-type]
        weapon_type=w["type"],
        trigger=d["trigger"],
        damage=damage,  # type: ignore[arg-type]
        critical_chance=d["criticalChance"],
        critical_multiplier=d["criticalMultiplier"],
        status_chance=d["procChance"],
        fire_rate=d["fireRate"],
        multishot=d["multishot"],
        magazine_size=d.get("magazineSize"),
        reload_time=d["reloadTime"],
        mastery_req=d["masteryReq"],
        riven_disposition=d["omegaAttenuation"],
        polarities=list(w.get("polarities") or []),
        exilus_polarity=w.get("exilusPolarity"),
        attacks=attacks,
        texture_location=texture,
    )


def _attack(a: dict[str, Any], weapon: str) -> Attack:
    unknown = set(a.get("damage", {})) - set(DAMAGE_TYPES)
    if unknown:
        raise RefreshError(f"{weapon} / {a.get('name')}: unknown damage types {sorted(unknown)}")
    falloff = a.get("falloff")
    return Attack(
        name=a["name"],
        fire_rate=a.get("speed"),
        critical_chance=a["crit_chance"] / 100,
        critical_multiplier=a["crit_mult"],
        status_chance=a["status_chance"] / 100,
        shot_type=a.get("shot_type"),
        damage={k: float(v) for k, v in a.get("damage", {}).items() if v},
        falloff=Falloff(**falloff) if falloff else None,
        charge_time=a.get("charge_time"),
        shot_speed=a.get("shot_speed"),
    )


def _slugs(items: list[tuple[str, str]]) -> dict[str, str]:
    base = {uid: slugify(name) for uid, name in items}
    counts = Counter(base.values())
    out = {}
    for uid, slug in base.items():
        out[uid] = slug if counts[slug] == 1 else f"{slug}-{slugify(uid.rsplit('/', 1)[-1])}"
    if len(set(out.values())) != len(out):
        raise RefreshError("weapon slug collision after disambiguation")
    return out


def _mods(
    upgrades: Any, mod_filter: dict[str, Any]
) -> tuple[list[Mod], list[ModSet], dict[str, int]]:
    rules = mod_filter["rules"]
    allow = set(mod_filter.get("allow", []))
    denied: Counter[str] = Counter()
    kept = []
    for m in _records(upgrades, "ExportUpgrades"):
        if m.get("type") not in GUN_MOD_TYPES:
            continue
        rule = None if m["uniqueName"] in allow else _deny_rule(m, rules)
        if rule:
            denied[rule] += 1
        elif not m.get("levelStats"):
            denied["no-level-stats"] += 1  # rivens (M2)
        else:
            kept.append(m)

    names: defaultdict[str, list[str]] = defaultdict(list)
    for m in kept:
        names[m["name"]].append(m["uniqueName"])
    dups = {n: u for n, u in names.items() if len(u) > 1}
    if dups:
        raise RefreshError(
            f"unclassified duplicate gun-mod names, add to reference/mod_filter.json:"
            f" {json.dumps(dups, indent=1)}"
        )

    mods = sorted(
        (
            Mod(
                unique_name=m["uniqueName"],
                name=m["name"],
                type=m["type"],
                compat_name=m.get("compatName") or "",
                polarity=m["polarity"],
                rarity=m["rarity"],
                base_drain=m["baseDrain"],
                fusion_limit=m["fusionLimit"],
                is_utility=bool(m.get("isUtility", False)),
                mod_set=m.get("modSet"),
                level_stats=[[clean_text(s) for s in lvl["stats"]] for lvl in m["levelStats"]],
            )
            for m in kept
        ),
        key=lambda m: m.unique_name,
    )
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


def _deny_rule(m: dict[str, Any], rules: list[dict[str, Any]]) -> str | None:
    for rule in rules:
        if rule["path_contains"] in m["uniqueName"]:
            prefix = rule.get("unless_name_starts")
            if prefix and m["name"].startswith(prefix):
                continue
            return str(rule["id"])
    return None


def _game_update(wfcd: list[dict[str, Any]]) -> str | None:
    dated = [
        (w["introduced"]["date"], w["introduced"]["name"])
        for w in wfcd
        if isinstance(w.get("introduced"), dict)
    ]
    return max(dated)[1] if dated else None


def _records(data: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        raise RefreshError(f"source format changed: no list `{key}`")
    return data[key]  # type: ignore[no-any-return]


def _list(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise RefreshError("source format changed: WFCD file is not a list")
    return data


def _reference(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RefreshError(f"{path}: expected an object")
    return data
