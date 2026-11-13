"""Read side of a release (PLAN C4): the `current` pointer, its manifest and builds."""

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from app.gamedata.builds import WeaponBuilds
from app.gamedata.updates import Updates, read_updates

POINTER = "current"
PRIMERS = "primers.json"  # {"good": [slugs]}: guns shown as good primers (G49)


def current(releases: Path) -> Path | None:
    """The folder `current` names; None before the first `wfb build-all`."""
    pointer = releases / POINTER
    if not pointer.exists():
        return None
    return releases / pointer.read_text().strip()


@dataclass(frozen=True)
class Release:
    folder: Path
    id: str
    dataset_hash: str

    @property
    def gamedata(self) -> Path:
        return self.folder / "gamedata"

    @cached_property
    def updates(self) -> Updates:
        """Read once: a release never changes."""
        return read_updates(self.folder)

    @cached_property
    def good_primers(self) -> frozenset[str]:
        """Empty for releases made before primers (G49)."""
        try:
            return frozenset(json.loads((self.folder / PRIMERS).read_bytes())["good"])
        except (OSError, ValueError, KeyError):
            return frozenset()

    def builds(self, slug: str) -> WeaponBuilds:
        """`slug` must be a known gun slug (it names a file)."""
        return WeaponBuilds.model_validate_json(
            (self.folder / "builds" / f"{slug}.json").read_bytes()
        )


def open_current(releases: Path) -> Release | None:
    folder = current(releases)
    if folder is None:
        return None
    manifest = json.loads((folder / "manifest.json").read_bytes())
    return Release(folder, manifest["id"], manifest["dataset_hash"])
