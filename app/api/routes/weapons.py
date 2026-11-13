"""GET /api/weapons: the gun list, filtered by category and a plain name search (S4)."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.schemas.lists import ExcludedWeapon, WeaponItem, WeaponList
from app.api.serving import served
from app.gamedata.images import image_path
from app.gamedata.models import Category
from app.gamedata.store import GameData

router = APIRouter()
# A gun waiting for source data (U7/U8): its detailed reason is for `wfb update` / `wfb check`.
PENDING = "New in the game: builds come with a later data update"


@router.get("/api/weapons")
def weapons(
    request: Request,
    category: Category | None = None,
    q: Annotated[str, Query(max_length=64)] = "",
) -> WeaponList:
    data: GameData = served(request).data
    needle = q.casefold()
    return WeaponList(
        dataset_hash=data.meta.dataset_hash,
        weapons=[
            WeaponItem(
                slug=w.slug,
                name=w.name,
                category=w.category,
                weapon_type=w.weapon_type,
                incarnon=w.unique_name in data.incarnon_by_id,
                progenitor=w.bonus_element is not None,
                mastery=w.mastery_req,
                image=f"/img/weapons/{w.slug}.png"
                if image_path(request.app.state.img_dir, w.slug).is_file()
                else None,
            )
            for w in sorted(data.weapons, key=lambda w: (w.name, w.slug))
            if (category is None or w.category == category) and needle in w.name.casefold()
        ],
        excluded=[
            ExcludedWeapon(name=e.name, reason=PENDING if e.pending else e.reason)
            for e in sorted(data.meta.excluded_weapons, key=lambda e: e.name)
            if needle in e.name.casefold()
        ],
    )
