"""Where a gun's icon lives in the image cache (written by refresh, served by /img)."""

from pathlib import Path


def image_path(img_dir: Path, slug: str) -> Path:
    return img_dir / "weapons" / f"{slug}.png"
