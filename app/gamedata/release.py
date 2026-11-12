"""Read side of a release (PLAN C4): the `current` pointer, its manifest and builds."""

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from app.gamedata.builds import WeaponBuilds
from app.gamedata.updates import Updates, read_updates

POINTER = "current"


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
