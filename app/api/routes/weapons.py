"""GET /api/weapons: the gun list, filtered by category and a plain name search (S4)."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from app.api.schemas.base import ApiError
from app.api.schemas.lists import ExcludedWeapon, WeaponItem, WeaponList
from app.api.serving import LISTS_KEPT, remember, served
from app.gamedata.images import image_path
from app.gamedata.models import Category
from app.gamedata.store import GameData

ERRORS: dict[int | str, dict[str, object]] = {429: {"model": ApiError}}

router = APIRouter()
# A gun waiting for source data (U7/U8): its detailed reason is for `wfb update` / `wfb check`.
PENDING = "New in the game: builds come with a later data update"


@router.get("/api/weapons", response_model=WeaponList, responses=ERRORS)
async def weapons(
    request: Request,
    category: Category | None = None,
    q: Annotated[str, Query(max_length=64)] = "",
) -> Response:
    """Answers without `q` (what the app asks for) are kept per release; building an answer
    counts against the per-address rate limit."""
    now = served(request)
    key = f"weapons:{category}"
    body = None if q else now.lists_cache.pop(key, None)
    if body is None:
        request.app.state.rate_limit.check(request)
        body = _list(now.data, request.app.state.img_dir, category, q).model_dump_json().encode()
    if not q:
        remember(now.lists_cache, key, body, LISTS_KEPT)
    return Response(body, media_type="application/json")


def _list(data: GameData, img_dir: Path, category: Category | None, q: str) -> WeaponList:
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
                if image_path(img_dir, w.slug).is_file()
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
