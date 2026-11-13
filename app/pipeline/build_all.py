"""`wfb build-all`: every gun's builds, in parallel, into a new release (PLAN Q28b, C4, G16).

Workers are spawned with `PYTHONHASHSEED=0` and each loads the dataset once. Results are
written as guns finish (one file each, manifest counts are order-free), so the release does
not depend on the worker count or finishing order. Guns whose input key matches the current
release's are copied from it instead of searched (G90 U3, `gun_inputs`).
"""

import itertools
import json
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from app.gamedata.builds import WeaponBuilds
from app.gamedata.release import current
from app.gamedata.store import GameData, load
from app.optimize.search import MAX_EVALUATIONS
from app.pipeline import release, search_pool
from app.pipeline.gun_inputs import INPUTS, gun_keys


@dataclass(frozen=True)
class Paths:
    gamedata: Path
    reference: Path
    releases: Path
    app: Path  # sources hashed into the calculator version (E10)

    @classmethod
    def project(cls, root: Path) -> "Paths":
        return cls(root / "gamedata", root / "reference", root / "cache/releases", root / "app")


def run(
    paths: Paths,
    workers: int | None = None,
    budget: int = MAX_EVALUATIONS,
    progress: Callable[[str], None] = lambda _: None,
) -> list[str]:
    started = time.monotonic()
    with release.lock(paths.releases):  # fail now, not after the night's work
        data = load(paths.gamedata)
        key = release.Key(
            data.meta.dataset_hash,
            release.tree_hash(paths.reference, "*.json"),
            release.calculator_version(paths.app),
            budget,
        )
        slugs = sorted(w.slug for w in data.weapons)
        keys = gun_keys(data, key.calculator, budget)
        previous = current(paths.releases)
        copied = _unchanged(previous, keys)
        todo = slowest_first(data, [s for s in slugs if s not in copied])
        workers = workers or os.cpu_count() or 1
        progress(
            f"build-all: {len(slugs)} guns, {len(todo)} to search, {len(copied)} unchanged "
            f"(copied from the current release); {workers} workers, budget {budget}; "
            "one line per searched gun (the first may take minutes); Ctrl+C stops"
        )
        assert previous is not None or not copied
        kept = (_read(previous, s) for s in sorted(copied)) if previous else iter(())
        folder = _publish(paths, data, key, keys, todo, kept, workers, budget, started, progress)
    minutes = (time.monotonic() - started) / 60
    return [
        f"release {key.id}: {len(slugs)} guns ({len(todo)} searched, {len(copied)} copied), "
        f"budget {budget}, {minutes:.1f} min",
        f"written to {folder}, now current",
    ]


def slowest_first(data: GameData, slugs: list[str]) -> list[str]:
    """Guns with a bonus element (one Recommended search per element) first, then Incarnon
    guns, then the rest: a long gun never runs alone at the end of the run."""

    def key(slug: str) -> tuple[bool, bool, str]:
        w = data.weapon_by_slug[slug]
        return (w.bonus_element is None, w.unique_name not in data.incarnon_by_id, slug)

    return sorted(slugs, key=key)


def _unchanged(previous: Path | None, keys: dict[str, str]) -> set[str]:
    """Guns whose input key matches the current release's and whose builds file is there."""
    if previous is None:
        return set()
    try:
        before = json.loads((previous / INPUTS).read_bytes())
    except (OSError, ValueError):
        return set()  # release made before U3, or unreadable: search every gun
    return {
        s
        for s, k in keys.items()
        if before.get(s) == k and (previous / "builds" / f"{s}.json").is_file()
    }


def _read(previous: Path, slug: str) -> WeaponBuilds:
    return WeaponBuilds.model_validate_json((previous / "builds" / f"{slug}.json").read_bytes())


def _publish(
    paths: Paths,
    data: GameData,
    key: release.Key,
    keys: dict[str, str],
    todo: list[str],
    kept: Iterator[WeaponBuilds],
    workers: int,
    budget: int,
    started: float,
    progress: Callable[[str], None],
) -> Path:
    def publish(searched: Iterator[WeaponBuilds]) -> Path:
        builds = itertools.chain(kept, _reported(searched, len(todo), started, progress))
        return release.publish(
            paths.releases, key, paths.gamedata, paths.reference, builds, set(keys), inputs=keys
        )

    return search_pool.search(data, paths.gamedata, todo, workers, budget, publish)


def _reported(
    results: Iterator[WeaponBuilds], total: int, started: float, progress: Callable[[str], None]
) -> Iterator[WeaponBuilds]:
    for done, b in enumerate(results, 1):
        progress(f"{done}/{total} {b.slug} ({(time.monotonic() - started) / 60:.1f} min)")
        yield b
