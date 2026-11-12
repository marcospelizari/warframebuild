"""Where cached pictures live (written by refresh, served by /img): gun icons by slug,
mod and arcane pictures by a hash of the DE id and texture (new picture, new name) plus
its file type."""

import hashlib
from pathlib import Path
from typing import Literal

PictureKind = Literal["mods", "arcanes"]
PICTURE_TYPES = {"png": "png", "jpg": "jpg", "jpeg": "jpg"}


def image_path(img_dir: Path, slug: str) -> Path:
    return img_dir / "weapons" / f"{slug}.png"


def picture_name(unique_name: str, texture_location: str | None) -> str | None:
    """`<16 hex>.<png|jpg>`, or None without a texture of a known type."""
    if not texture_location:
        return None
    ext = PICTURE_TYPES.get(texture_location.split("!", 1)[0].rsplit(".", 1)[-1].lower())
    if ext is None:
        return None
    digest = hashlib.sha256(f"{unique_name}\n{texture_location}".encode()).hexdigest()
    return f"{digest[:16]}.{ext}"


def picture_path(img_dir: Path, kind: PictureKind, name: str) -> Path:
    return img_dir / kind / name
