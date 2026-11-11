"""`wfb build-all`: every gun's builds, in parallel, into a new release (PLAN Q28b, C4, G16).

Workers are spawned with `PYTHONHASHSEED=0` and each loads the dataset once. Results come
back in slug order, so the release does not depend on the worker count.
"""

import multiprocessing
import os
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from app.gamedata.builds import WeaponBuilds
from app.gamedata.store import GameData, load
from app.optimize.builds import weapon_builds
from app.optimize.search import MAX_EVALUATIONS
from app.pipeline import release

_data: GameData | None = None
_error: str | None = None  # why this worker's dataset is unusable


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
        seed = os.environ.get("PYTHONHASHSEED")
        os.environ["PYTHONHASHSEED"] = "0"  # inherited by the spawned workers only (G16)
        try:
            with ProcessPoolExecutor(
                workers,
                mp_context=multiprocessing.get_context("spawn"),
                initializer=_load,
                initargs=(paths.gamedata, key.dataset),
            ) as pool:
                try:
                    results = pool.map(_one, slugs, [budget] * len(slugs))
                    folder = release.publish(
                        paths.releases,
                        key,
                        paths.gamedata,
                        paths.reference,
                        _reported(results, len(slugs), started, progress),
                        set(slugs),
                    )
                except BaseException:
                    pool.shutdown(cancel_futures=True)
                    raise
        finally:
            if seed is None:
                del os.environ["PYTHONHASHSEED"]
            else:
                os.environ["PYTHONHASHSEED"] = seed
    minutes = (time.monotonic() - started) / 60
    return [
        f"release {key.id}: {len(slugs)} guns, budget {budget}, {minutes:.1f} min",
        f"written to {folder}, now current",
    ]


def _reported(
    results: Iterator[WeaponBuilds], total: int, started: float, progress: Callable[[str], None]
) -> Iterator[WeaponBuilds]:
    for done, b in enumerate(results, 1):
        progress(f"{done}/{total} {b.slug} ({(time.monotonic() - started) / 60:.1f} min)")
        yield b


def _load(gamedata: Path, dataset: str) -> None:
    """Never raises: a failing initializer breaks the pool and hides the reason."""
    global _data, _error
    try:
        _data = load(gamedata)
        if _data.meta.dataset_hash != dataset:
            _error = f"gamedata/ changed during the run ({dataset} -> {_data.meta.dataset_hash})"
    except Exception as error:
        _error = f"worker could not load gamedata/: {error}"


def _one(slug: str, budget: int) -> WeaponBuilds:
    if _error or _data is None:
        raise release.ReleaseError(_error or "worker started without its dataset")
    return weapon_builds(_data, _data.weapon_by_slug[slug], budget)
