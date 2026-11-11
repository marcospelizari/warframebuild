"""GET /img/weapons/{name}: cached gun icons. `name` must be a known `<slug>.png` and is
never joined into a path as given (S2)."""

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.api.errors import ApiFailure
from app.gamedata.images import image_path
from app.gamedata.store import GameData

router = APIRouter()


@router.get("/img/weapons/{name}", include_in_schema=False)
def icon(name: str, request: Request) -> FileResponse:
    data: GameData = request.app.state.data
    slug = name.removesuffix(".png")
    weapon = data.weapon_by_slug.get(slug) if name.endswith(".png") else None
    path = image_path(request.app.state.img_dir, weapon.slug) if weapon else None
    if path is None or not path.is_file():
        raise ApiFailure(404, "unknown_image", "no such image")
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
