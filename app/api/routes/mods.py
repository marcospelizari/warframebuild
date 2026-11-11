"""GET /api/mods?weapon=<slug>: what the editor may offer for one gun (F7, G20)."""

from fastapi import APIRouter, Query, Request

from app.api.build_response import weapon_ref
from app.api.errors import ApiFailure
from app.api.schemas import ApiError, ArcaneItem, ModItem, ModList, PerkItem, PerkTier
from app.gamedata.store import GameData
from app.optimize.candidates import arcane_fits, fits

ERRORS: dict[int | str, dict[str, object]] = {404: {"model": ApiError}}

router = APIRouter()


@router.get("/api/mods", responses=ERRORS)
def mods(request: Request, weapon: str = Query(max_length=100)) -> ModList:
    data: GameData = request.app.state.data
    gun = data.weapon_by_slug.get(weapon)
    if gun is None:
        raise ApiFailure(404, "unknown_weapon", "no such weapon", "weapon")
    unfit = f"does not fit {gun.name}"
    incarnon = data.incarnon_by_id.get(gun.unique_name)
    perks = incarnon.perks if incarnon else []
    return ModList(
        dataset_hash=data.meta.dataset_hash,
        weapon=weapon_ref(gun),
        mods=[
            ModItem(
                unique_name=m.unique_name,
                name=m.name,
                polarity=m.polarity,
                rarity=m.rarity,
                rank=m.fusion_limit,
                drain=m.base_drain + m.fusion_limit,
                exilus=m.exilus,
                family=m.family,
                mod_set=m.mod_set,
                support=m.effects.support,
                stats=m.level_stats[-1] if m.level_stats else [],
                description=m.description,
                compatible=ok,
                reason=None if ok else unfit,
            )
            for m in sorted(data.mods.mods, key=lambda m: (m.name, m.unique_name))
            if m.category == gun.category
            for ok in (fits(gun, m),)
        ],
        arcanes=[
            ArcaneItem(
                unique_name=a.unique_name,
                name=a.name,
                rarity=a.rarity,
                support=a.effects.support,
                stats=a.level_stats[-1] if a.level_stats else [],
                compatible=ok,
                reason=None if ok else f"{a.weapon_type} only",
            )
            for a in sorted(data.arcanes, key=lambda a: (a.name, a.unique_name))
            if a.category == gun.category
            for ok in (arcane_fits(gun, a),)
        ],
        perks=[
            PerkTier(
                tier=tier,
                options=[
                    PerkItem(name=p.name, form=p.form, support=p.effects.support)
                    for p in perks
                    if p.tier == tier
                ],
            )
            for tier in sorted({p.tier for p in perks})
        ],
    )
