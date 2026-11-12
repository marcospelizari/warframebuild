"""GET /img/...: cached pictures and the saved wiki card art. A name is looked up in a
known set, or must be a plain file name inside a fixed folder; never joined into a path
as given (S2)."""

import re
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.api.errors import ApiFailure
from app.gamedata.images import PictureKind, image_path, picture_path
from app.gamedata.store import GameData

router = APIRouter()

CACHE_FOREVER = {"Cache-Control": "public, max-age=31536000, immutable"}
MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}
KINDS: dict[str, PictureKind] = {"mods": "mods", "arcanes": "arcanes"}
# Folders of cache/raw/wiki/img/ the UI uses (README there); no SVG (it can carry script).
ART_FOLDERS = frozenset({"mod-card", "mod-slot", "polarity", "arcane", "damage"})
ART_NAME = re.compile(r"[A-Za-z0-9_-]{1,80}\.(png|webp)")


def _missing() -> ApiFailure:
    return ApiFailure(404, "unknown_image", "no such image")


def _file(path: Path) -> FileResponse:
    if not path.is_file():
        raise _missing()
    return FileResponse(path, media_type=MEDIA[path.suffix], headers=CACHE_FOREVER)


@router.get("/img/weapons/{name}", include_in_schema=False)
def icon(name: str, request: Request) -> FileResponse:
    data: GameData = request.app.state.data
    weapon = data.weapon_by_slug.get(name.removesuffix(".png")) if name.endswith(".png") else None
    if weapon is None:
        raise _missing()
    return _file(image_path(request.app.state.img_dir, weapon.slug))


@router.get("/img/{kind}/{name}", include_in_schema=False)
def picture(kind: str, name: str, request: Request) -> FileResponse:
    data: GameData = request.app.state.data
    known = KINDS.get(kind)
    if known is None or name not in data.picture_names[known]:
        raise _missing()
    return _file(picture_path(request.app.state.img_dir, known, name))


@router.get("/img/art/{folder}/{name}", include_in_schema=False)
def art(folder: str, name: str, request: Request) -> FileResponse:
    if folder not in ART_FOLDERS or not ART_NAME.fullmatch(name):
        raise _missing()
    return _file(request.app.state.art_dir / folder / name)
