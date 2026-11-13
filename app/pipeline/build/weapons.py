"""Guns: DE ExportWeapons (canonical) joined with WFCD Primary/Secondary on uniqueName (E5)."""

import re
from collections import Counter
from typing import Any

from pydantic import ValidationError

from app.domain.polarity import Polarity
from app.gamedata.meta import Exclusion, Join
from app.gamedata.models import BonusElement, Weapon
from app.pipeline.build.attacks import attack
from app.pipeline.build.direct_bonus import DirectBonusTable
from app.pipeline.build.effects import Overrides
from app.pipeline.build.fire import FireOverrides, attack_data, fire_rate
from app.pipeline.build.gaps import Gaps
from app.pipeline.errors import DataGap, RefreshError
from app.pipeline.sources.de_export import (
    DAMAGE_SLOT_COUNT,
    DAMAGE_SLOTS,
    DEFAULT_MAX_RANK,
    WEAPON_CATEGORY,
)
from app.pipeline.sources.export_plus import known
from app.pipeline.sources.wfcd import POLARITIES
from app.pipeline.sources.wiki_progenitor import Progenitor
from app.pipeline.sources.wiki_weapon_data import WeaponData


def build(
    de_weapons: list[dict[str, Any]],
    wfcd: list[dict[str, Any]],
    textures: dict[str, str | None],
    fire: FireOverrides,
    tags: dict[str, list[str]],
    module: dict[str, WeaponData],
    direct: DirectBonusTable,
    progenitor: dict[str, Progenitor],
    overrides: Overrides,
    gaps: Gaps,
) -> tuple[list[Weapon], list[Exclusion], list[Join]]:
    """`gaps` collects new guns whose data is incomplete (U7/U8)."""
    de = {w["uniqueName"]: w for w in de_weapons}
    by_id: dict[str, dict[str, Any]] = {}
    for w in wfcd:
        if w["uniqueName"] in by_id:
            raise RefreshError(f"duplicate WFCD entry: {w['uniqueName']}")
        by_id[w["uniqueName"]] = w
    for uid in sorted(u for u in by_id if u not in de):
        gaps.exclude(uid, by_id[uid]["name"], DataGap("in WFCD's data, not in the game files"))
    de_guns = {
        u for u, w in de.items() if w.get("productCategory") in WEAPON_CATEGORY and w.get("trigger")
    }
    for uid in sorted(de_guns - by_id.keys()):
        gaps.exclude(uid, de[uid]["name"], DataGap("in the game files, not in WFCD's data yet"))

    kept: list[tuple[dict[str, Any], dict[str, Any]]] = []
    excluded: list[Exclusion] = []
    for uid in sorted(u for u in by_id if u in de):
        d, w = de[uid], by_id[uid]
        reason = None
        if d["productCategory"] not in WEAPON_CATEGORY:
            reason = f"not a primary or secondary gun (DE category {d['productCategory']})"
        else:
            reason = fire.excluded(uid)
        if reason:
            excluded.append(Exclusion(unique_name=uid, name=d["name"], reason=reason))
        else:
            kept.append((d, w))

    fire.check_known(set(by_id) | de_guns)
    direct.check(
        {d["uniqueName"]: [a["name"] for a in w.get("attacks") or []] for d, w in kept}, gaps.ids
    )
    slugs = _slugs([(d["uniqueName"], d["name"]) for d, _ in kept])
    weapons = []
    for d, w in kept:
        uid = d["uniqueName"]
        try:
            weapons.append(_weapon(d, w, slugs[uid], textures.get(uid), tags, fire, module, direct))
        except DataGap as gap:
            gaps.exclude(uid, d["name"], gap)
    kept = [(d, w) for d, w in kept if d["uniqueName"] not in gaps.ids]
    weapons = [_with_bonus(x, progenitor.get(x.name)) for x in weapons]
    weapons = [_with_zoom(x, module.get(x.unique_name), overrides) for x in weapons]
    joins = [
        Join(unique_name=d["uniqueName"], de_name=d["name"], wfcd_name=w["name"]) for d, w in kept
    ]
    return weapons, excluded, joins


def _weapon(
    d: dict[str, Any],
    w: dict[str, Any],
    slug: str,
    texture: str | None,
    tags: dict[str, list[str]],
    fire: FireOverrides,
    module: dict[str, WeaponData],
    direct: DirectBonusTable,
) -> Weapon:
    per_shot = d["damagePerShot"]
    if len(per_shot) != DAMAGE_SLOT_COUNT:
        raise RefreshError(
            f"{d['name']}: damagePerShot has {len(per_shot)} entries, expected {DAMAGE_SLOT_COUNT}"
        )
    if any(per_shot[len(DAMAGE_SLOTS) :]):
        raise RefreshError(f"{d['name']}: damage in an unmapped damagePerShot slot")
    damage = {t: float(v) for t, v in zip(DAMAGE_SLOTS, per_shot, strict=False) if v}
    category = WEAPON_CATEGORY[d["productCategory"]]
    data = module.get(d["uniqueName"])
    extra = attack_data([a["name"] for a in w.get("attacks") or []], data)
    if w.get("category", "").lower() != category:
        raise DataGap(f"the game files say {category}, WFCD says {w.get('category')}")
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
            fire_rate=fire_rate(d, data),
            multishot=d["multishot"],
            magazine_size=_magazine(d, data),
            reload_time=fire.reload_time(d["uniqueName"], d["reloadTime"]),
            mastery_req=d["masteryReq"],
            riven_disposition=d["omegaAttenuation"],
            polarities=[_polarity(x, d["name"]) for x in w.get("polarities") or []],
            exilus_polarity=_polarity(w["exilusPolarity"], d["name"])
            if w.get("exilusPolarity")
            else None,
            max_rank=d.get("maxLevelCap", DEFAULT_MAX_RANK),
            # WFCD lists each attack (charged, per pellet, AoE part); DE gives one summary,
            # so values legitimately differ. The main attack is chosen later (main_attack.json).
            attacks=[
                attack(
                    a,
                    d["name"],
                    extra[a["name"]],
                    direct.behaviour(d["uniqueName"], a["name"], a.get("shot_type")),
                    fire.attack_beam_start(
                        d["uniqueName"], d["name"], d["trigger"], extra[a["name"]]
                    ),
                )
                for a in w.get("attacks") or []
            ],
            texture_location=texture,
            # export-plus can lag DE after an update: unknown tags stay None (report lists them).
            compatibility_tags=known(tags[d["uniqueName"]], d["name"])
            if d["uniqueName"] in tags
            else None,
            sniper_combo_min=data.sniper_combo_min if data else None,
            no_reload=fire.no_reload(d["uniqueName"]),
            reload_replaces_shot=fire.reload_replaces_shot(d["uniqueName"]),
            beam_ramp_start=fire.beam_start(d["uniqueName"], d["name"], d["trigger"]),
            bonus_element=None,
        )
    except ValidationError as error:
        raise RefreshError(f"{d['name']}: invalid values: {error}") from error


def _with_bonus(weapon: Weapon, p: Progenitor | None) -> Weapon:
    if p is None:
        return weapon
    bonus = BonusElement(elements=list(p.elements), max_share=p.max_share, page=p.page)
    return weapon.model_copy(update={"bonus_element": bonus})


def _with_zoom(weapon: Weapon, data: WeaponData | None, overrides: Overrides) -> Weapon:
    """Zoom bonus lines parsed like mod text; exceptions (Lanka) in overrides.json `#zoom`."""
    if data is None or not data.zoom:
        return weapon
    effects = overrides.effects(f"{weapon.unique_name}#zoom", data.zoom)
    return weapon.model_copy(update={"zoom": effects})


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


_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    return _SLUG.sub("-", name.lower()).strip("-")


def _magazine(d: dict[str, Any], data: WeaponData | None) -> int | None:
    """DE magazine size, else the wiki module's (0 there = no magazine -> None). Unknown
    fails the refresh: treating it as "no magazine" would mean "never reloads"."""
    size = d.get("magazineSize")
    if size is not None:
        return int(size)
    if data is None or data.magazine is None:
        raise DataGap(
            "no magazine size in the game files or the wiki weapon data "
            "(or exclude it in reference/fire_overrides.json until known)"
        )
    return data.magazine or None


def _polarity(name: str, gun: str) -> Polarity:
    if name not in POLARITIES:
        raise RefreshError(f"{gun}: unknown WFCD polarity {name!r} (add it to wfcd.POLARITIES)")
    return POLARITIES[name]
