"""Read side of a release (PLAN C4): the `current` pointer, its manifest and builds."""

import hashlib
import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from app.gamedata.builds import WeaponBuilds
from app.gamedata.updates import Updates, read_updates

APP = Path(__file__).resolve().parents[1]  # the `app` package
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


class StaleRelease(ValueError):
    """The release was built by other calculator code than the one running."""


def open_current(releases: Path, calculator: str | None = None) -> Release | None:
    """`calculator`: the running code's version (default: this checkout's); a release built
    by other code fails, so stale builds are never served as current (E10)."""
    folder = current(releases)
    if folder is None:
        return None
    manifest = json.loads((folder / "manifest.json").read_bytes())
    expected = calculator or calculator_version(APP)
    if manifest["calculator_version"] != expected:
        raise StaleRelease(
            f"built by calculator {manifest['calculator_version']}, running {expected}"
        )
    return Release(folder, manifest["id"], manifest["dataset_hash"])


def tree_hash(folder: Path, pattern: str) -> str:
    """Hash of every file matching `pattern` under `folder`: relative path + bytes, sorted."""
    digest = hashlib.sha256()
    for path in sorted(folder.rglob(pattern)):
        digest.update(path.relative_to(folder).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()[:16]


def calculator_version(app_dir: Path) -> str:
    """E10: changes with any source change in `domain`, `optimize`, or `gamedata` (the build
    file format)."""
    digest = hashlib.sha256()
    for layer in ("domain", "gamedata", "optimize"):
        digest.update(tree_hash(app_dir / layer, "*.py").encode())
    return digest.hexdigest()[:16]
