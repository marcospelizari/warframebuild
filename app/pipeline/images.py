"""Gun icons and mod / arcane pictures from DE ExportManifest into cache/img/ (never
committed)."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.gamedata.images import PictureKind, image_path, picture_name, picture_path
from app.gamedata.models import Arcane, Mod, Weapon
from app.pipeline.sources import atomic_write
from app.pipeline.sources.de_export import BASE_URL
from app.pipeline.sources.http import DownloadError, PoliteClient

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAGIC = {".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff"}


@dataclass(frozen=True)
class Picture:
    label: str
    texture: str
    path: Path


def weapon_pictures(weapons: list[Weapon], img_dir: Path) -> list[Picture]:
    return [
        Picture(w.name, w.texture_location, image_path(img_dir, w.slug))
        for w in weapons
        if w.texture_location
    ]


def item_pictures(kind: PictureKind, items: Sequence[Mod | Arcane], img_dir: Path) -> list[Picture]:
    out = []
    for item in items:
        name = picture_name(item.unique_name, item.texture_location)
        if name and item.texture_location:
            out.append(Picture(item.name, item.texture_location, picture_path(img_dir, kind, name)))
    return out


def fetch_missing(client: PoliteClient, pictures: list[Picture]) -> list[str]:
    """Download pictures not cached yet. Returns failures as messages (refresh still
    succeeds)."""
    failures = []
    for picture in pictures:
        if picture.path.exists():
            continue
        try:
            data = client.get(f"{BASE_URL}{picture.texture}", max_bytes=MAX_IMAGE_BYTES)
        except DownloadError as error:
            failures.append(f"{picture.label}: {error}")
            continue
        if not data.startswith(MAGIC[picture.path.suffix]):
            failures.append(f"{picture.label}: not a {picture.path.suffix[1:].upper()}")
            continue
        atomic_write(picture.path, data)
    return failures
