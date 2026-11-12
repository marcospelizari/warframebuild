"""Releases of precomputed builds (PLAN C4, E10).

`cache/releases/<id>/` holds copies of `gamedata/` and `reference/`, `builds/<slug>.json`
and `manifest.json`. The id is the cache key: dataset hash, reference hash, calculator
version (hash of the `domain`, `gamedata` and `optimize` sources) and the search budget.
A release is written into a hidden temp folder, validated, renamed, and only then does the `current`
pointer file switch to it; an interrupted run leaves `current` unchanged. The last
`KEEP` releases stay.
"""

import datetime
import hashlib
import os
import shutil
from collections import Counter
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.gamedata.builds import WeaponBuilds
from app.gamedata.release import POINTER, current
from app.gamedata.store import load
from app.pipeline import updates
from app.pipeline.gun_inputs import INPUTS
from app.pipeline.publish import dump, exclusive

KEEP = 2


class ReleaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class Key:
    dataset: str
    reference: str
    calculator: str
    budget: int

    @property
    def id(self) -> str:
        text = f"{self.dataset}\0{self.reference}\0{self.calculator}\0{self.budget}"
        return hashlib.sha256(text.encode()).hexdigest()[:16]


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


@contextmanager
def lock(releases: Path) -> Iterator[None]:
    """Held for a whole build-all run, before any work starts."""
    releases.mkdir(parents=True, exist_ok=True)
    with exclusive(releases / ".lock", "build-all"):
        yield


def publish(
    releases: Path,
    key: Key,
    gamedata: Path,
    reference: Path,
    builds: Iterable[WeaponBuilds],
    expected: set[str],
    today: str | None = None,
    inputs: dict[str, str] | None = None,
) -> Path:
    """Write the release from `builds` (consumed as they come), validate, switch `current`.
    `expected`: the slug of every gun that must have builds. The caller holds `lock`.
    `updates.json` compares it with the current release (U10); `inputs` (per-gun input
    keys, U3) goes to `inputs.json` for the next incremental run."""
    for old in releases.glob(".*.tmp.old"):  # crash between the two renames below
        live = releases / old.name.removeprefix(".").removesuffix(".tmp.old")
        if not live.exists():
            old.rename(live)
    for leftover in releases.glob(".*.tmp*"):  # interrupted runs; none is running (`lock`)
        if leftover.is_dir():
            shutil.rmtree(leftover)
        else:
            leftover.unlink()
    final = releases / key.id
    temp = releases / f".{key.id}.tmp"
    shutil.copytree(gamedata, temp / "gamedata")
    copied = load(temp / "gamedata").meta.dataset_hash
    if copied != key.dataset:
        raise ReleaseError(f"gamedata/ changed during the run ({key.dataset} -> {copied})")
    shutil.copytree(reference, temp / "reference")
    (temp / "builds").mkdir()
    statuses: Counter[str] = Counter()
    unplaced = 0
    for b in builds:
        (temp / "builds" / f"{b.slug}.json").write_bytes(dump(b))
        for v in b.variants:
            for build in (v.max, v.recommended, *v.factions.values()):
                statuses[build.status] += 1
                unplaced += build.forma is None
    _validate(temp / "builds", expected)
    manifest = {
        "id": key.id,
        "dataset_hash": key.dataset,
        "reference_hash": key.reference,
        "calculator_version": key.calculator,
        "budget": key.budget,
        "weapons": len(expected),
        "builds": dict(sorted(statuses.items())),
        "no_forma_layout": unplaced,
    }
    (temp / "manifest.json").write_bytes(dump(manifest))
    if inputs is not None:
        (temp / INPUTS).write_bytes(dump(dict(sorted(inputs.items()))))
    updates.write(temp, current(releases), key.id, today or datetime.date.today().isoformat())
    old = releases / f".{key.id}.tmp.old"  # same key again: the live copy goes last
    if final.exists():
        final.rename(old)
    temp.rename(final)
    _point(releases, key.id)
    shutil.rmtree(old, ignore_errors=True)
    _prune(releases, key.id)
    return final


def _validate(builds: Path, expected: set[str]) -> None:
    found = {p.stem for p in builds.glob("*.json")}
    if found != expected:
        missing = sorted(expected - found)
        extra = sorted(found - expected)
        raise ReleaseError(f"builds do not match the guns: missing {missing}, extra {extra}")
    for p in sorted(builds.glob("*.json")):
        WeaponBuilds.model_validate_json(p.read_bytes())


def _point(releases: Path, release_id: str) -> None:
    temp = releases / f".{POINTER}.tmp"
    temp.write_text(release_id + "\n")
    os.replace(temp, releases / POINTER)


def _prune(releases: Path, keep_id: str) -> None:
    """Keep `current` and the newest others, `KEEP` in all."""
    others = [p for p in releases.iterdir() if p.is_dir() and not p.name.startswith(".")]
    others = sorted(
        (p for p in others if p.name != keep_id), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for old in others[KEEP - 1 :]:
        shutil.rmtree(old)
