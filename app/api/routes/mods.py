"""GET /api/mods?weapon=<slug>: what the editor may offer for one gun (F7, G20). Answers
are kept per release; building one counts against the per-address rate limit."""

from pathlib import Path

from fastapi import APIRouter, Query, Request, Response

from app.api.build_response import weapon_ref
from app.api.errors import ApiFailure
from app.api.schemas.base import ApiError
from app.api.schemas.lists import ArcaneItem, ModItem, ModList, PerkItem, PerkTier
from app.api.serving import LISTS_KEPT, remember, served
from app.gamedata.images import PictureKind, picture_name, picture_path
from app.gamedata.models import Arcane, Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.candidates import arcane_fits, fits

ERRORS: dict[int | str, dict[str, object]] = {404: {"model": ApiError}, 429: {"model": ApiError}}

router = APIRouter()


def _image(img_dir: Path, kind: PictureKind, item: Mod | Arcane) -> str | None:
    name = picture_name(item.unique_name, item.texture_location)
    if name is None or not picture_path(img_dir, kind, name).is_file():
        return None
    return f"/img/{kind}/{name}"


@router.get("/api/mods", response_model=ModList, responses=ERRORS)
async def mods(request: Request, weapon: str = Query(max_length=100)) -> Response:
    now = served(request)
    gun = now.data.weapon_by_slug.get(weapon)
    if gun is None:
        raise ApiFailure(404, "unknown_weapon", "no such weapon", "weapon")
    key = f"mods:{gun.slug}"
    body = now.lists_cache.pop(key, None)
    if body is None:
        request.app.state.rate_limit.check(request)
        body = _mod_list(now.data, gun, request.app.state.img_dir).model_dump_json().encode()
    remember(now.lists_cache, key, body, LISTS_KEPT)
    return Response(body, media_type="application/json")


def _mod_list(data: GameData, gun: Weapon, img_dir: Path) -> ModList:
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
                image=_image(img_dir, "mods", m),
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
                image=_image(img_dir, "arcanes", a),
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
