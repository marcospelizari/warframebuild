"""Weapon icons from DE ExportManifest into cache/img/ (never committed)."""

from pathlib import Path

from app.data.http import DownloadError, PoliteClient
from app.data.models import Weapon
from app.data.sources.de_export import BASE_URL

MAX_IMAGE_BYTES = 4 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def image_path(img_dir: Path, weapon: Weapon) -> Path:
    return img_dir / "weapons" / f"{weapon.slug}.png"


def fetch_missing(client: PoliteClient, weapons: list[Weapon], img_dir: Path) -> list[str]:
    """Download icons not cached yet. Returns failures as messages (refresh still succeeds)."""
    failures = []
    (img_dir / "weapons").mkdir(parents=True, exist_ok=True)
    for weapon in weapons:
        path = image_path(img_dir, weapon)
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
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)
    return failures
