"""Guns: DE ExportWeapons (canonical) joined with WFCD Primary/Secondary on uniqueName (E5)."""

from collections import Counter
from typing import Any

from pydantic import ValidationError

from app.data.build.common import RefreshError, slugify
from app.data.models import Attack, DamageType, Exclusion, Falloff, Join, Weapon
from app.data.sources.de_export import DAMAGE_SLOT_COUNT, DAMAGE_SLOTS, WEAPON_CATEGORY


def build(
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
        u for u, w in de.items() if w.get("productCategory") in WEAPON_CATEGORY and w.get("trigger")
    }
    missing = sorted(de_guns - by_id.keys())
    if missing:
        raise RefreshError(f"DE guns missing in WFCD: {[de[u]['name'] for u in missing]}")

    kept: list[tuple[dict[str, Any], dict[str, Any]]] = []
    excluded: list[Exclusion] = []
    for uid in sorted(by_id):
        d, w = de[uid], by_id[uid]
        reason = None
        if d["productCategory"] not in WEAPON_CATEGORY:
            reason = f"not a primary or secondary gun (DE category {d['productCategory']})"
        elif "exclude" in fire_overrides.get(uid, {}):
            reason = str(fire_overrides[uid]["exclude"])
        elif not d.get("fireRate") or d["fireRate"] <= 0:
            raise RefreshError(
                f"{d['name']} ({uid}): no usable fire rate. Add an `exclude` entry with the "
                "reason to reference/fire_overrides.json until real values are known."
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
    per_shot = d["damagePerShot"]
    if len(per_shot) != DAMAGE_SLOT_COUNT:
        raise RefreshError(
            f"{d['name']}: damagePerShot has {len(per_shot)} entries, expected {DAMAGE_SLOT_COUNT}"
        )
    if any(per_shot[len(DAMAGE_SLOTS) :]):
        raise RefreshError(f"{d['name']}: damage in an unmapped damagePerShot slot")
    damage = {t: float(v) for t, v in zip(DAMAGE_SLOTS, per_shot, strict=False) if v}
    category = WEAPON_CATEGORY[d["productCategory"]]
    if w.get("category", "").lower() != category:
        raise RefreshError(f"{d['name']}: DE says {category}, WFCD says {w.get('category')}")
    try:
        return Weapon(
            unique_name=d["uniqueName"],
            slug=slug,
            name=d["name"],
            category=category,
            weapon_type=w["type"],
            trigger=d["trigger"],
            damage=damage,
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
            # WFCD lists each attack (charged, per pellet, AoE part); DE gives one summary,
            # so values legitimately differ. The main attack is chosen later (main_attack.json).
            attacks=[_attack(a, d["name"]) for a in w.get("attacks") or []],
            texture_location=texture,
        )
    except ValidationError as error:
        raise RefreshError(f"{d['name']}: invalid values: {error}") from error


def _attack(a: dict[str, Any], weapon: str) -> Attack:
    known = {t.value for t in DamageType}
    unknown = set(a.get("damage", {})) - known
    if unknown:
        raise RefreshError(f"{weapon} / {a.get('name')}: unknown damage types {sorted(unknown)}")
    falloff = a.get("falloff")
    try:
        return _attack_model(a, falloff)
    except ValidationError as error:
        raise RefreshError(f"{weapon} / {a.get('name')}: invalid values: {error}") from error


def _attack_model(a: dict[str, Any], falloff: dict[str, Any] | None) -> Attack:
    return Attack(
        name=a["name"],
        # WFCD uses speed 0 on DoT pseudo-attacks (e.g. Tysis "Corrosive DoT"): no own rate.
        fire_rate=a.get("speed") or None,
        critical_chance=a["crit_chance"] / 100,
        critical_multiplier=a["crit_mult"],
        status_chance=a["status_chance"] / 100,
        shot_type=a.get("shot_type"),
        damage={DamageType(k): float(v) for k, v in a.get("damage", {}).items() if v},
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


def game_update(wfcd: list[dict[str, Any]]) -> str | None:
    dated = [
        (w["introduced"]["date"], w["introduced"]["name"])
        for w in wfcd
        if isinstance(w.get("introduced"), dict)
    ]
    return max(dated)[1] if dated else None
