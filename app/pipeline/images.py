"""Weapon icons from DE ExportManifest into cache/img/ (never committed)."""

from pathlib import Path

from app.gamedata.images import image_path
from app.gamedata.models import Weapon
from app.pipeline.sources import atomic_write
from app.pipeline.sources.de_export import BASE_URL
from app.pipeline.sources.http import DownloadError, PoliteClient

MAX_IMAGE_BYTES = 4 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def fetch_missing(client: PoliteClient, weapons: list[Weapon], img_dir: Path) -> list[str]:
    """Download icons not cached yet. Returns failures as messages (refresh still succeeds)."""
    failures = []
    for weapon in weapons:
        path = image_path(img_dir, weapon.slug)
        if path.exists() or not weapon.texture_location:
            continue
        try:
            data = client.get(f"{BASE_URL}{weapon.texture_location}", max_bytes=MAX_IMAGE_BYTES)
        except DownloadError as error:
            failures.append(f"{weapon.name}: {error}")
            continue
        if not data.startswith(PNG_MAGIC):
            failures.append(f"{weapon.name}: not a PNG")
            continue
        atomic_write(path, data)
    return failures
