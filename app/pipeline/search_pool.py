"""Worker processes for build-all and sample: each gun's plan (optimize.builds.plan) is
split into single searches, so one gun can use many workers and no long gun runs alone
at the end. A gun already started gets its next tasks before a new gun starts."""

import multiprocessing
import os
import time
from collections import deque
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from pathlib import Path

from app.gamedata.builds import WeaponBuilds
from app.gamedata.store import GameData, load
from app.optimize.builds import Found, Plan, Task, plan, run
from app.pipeline import release

_data: GameData | None = None  # per worker process
_error: str | None = None


def search[T](
    data: GameData,
    gamedata: Path,
    slugs: list[str],
    workers: int,
    budget: int,
    consume: Callable[[Iterator[WeaponBuilds]], T],
    busy: dict[str, float] | None = None,
) -> T:
    """Search `slugs` (started in this order); `consume` gets each gun's builds when its
    last task ends. `busy`, if given, gets each gun's summed task time in seconds."""
    if not slugs:
        return consume(iter(()))
    seed = os.environ.get("PYTHONHASHSEED")
    os.environ["PYTHONHASHSEED"] = "0"  # inherited by the spawned workers only (G16)
    try:
        with ProcessPoolExecutor(
            workers,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_load,
            initargs=(gamedata, data.meta.dataset_hash),
        ) as pool:
            try:
                return consume(
                    _scheduled(pool, data, slugs, workers, budget, {} if busy is None else busy)
                )
            except BaseException:
                _stop(pool)
                raise
    finally:
        if seed is None:
            del os.environ["PYTHONHASHSEED"]
        else:
            os.environ["PYTHONHASHSEED"] = seed


def _scheduled(
    pool: ProcessPoolExecutor,
    data: GameData,
    slugs: list[str],
    workers: int,
    budget: int,
    busy: dict[str, float],
) -> Iterator[WeaponBuilds]:
    new = deque(slugs)
    ready: deque[tuple[str, int, Task]] = deque()  # started guns' tasks first
    plans: dict[str, Plan] = {}
    answers: dict[str, list[Found | None]] = {}
    running: dict[Future[tuple[Found, float]], tuple[str, int]] = {}

    def queue(slug: str, batch: list[Task]) -> None:
        answers[slug] = [None] * len(batch)
        ready.extendleft(reversed([(slug, i, t) for i, t in enumerate(batch)]))

    while True:
        while len(running) < workers and (ready or new):
            if not ready:
                slug = new.popleft()
                plans[slug] = plan(data, data.weapon_by_slug[slug])
                queue(slug, next(plans[slug]))
                continue
            slug, i, task = ready.popleft()
            running[pool.submit(_task, slug, task, budget)] = (slug, i)
        if not running:
            return
        done, _ = wait(running, return_when=FIRST_COMPLETED)
        for future in done:
            slug, i = running.pop(future)
            found, seconds = future.result()
            busy[slug] = busy.get(slug, 0.0) + seconds
            answers[slug][i] = found
            if any(a is None for a in answers[slug]):
                continue
            batch = [a for a in answers.pop(slug) if a is not None]
            try:
                queue(slug, plans[slug].send(batch))
            except StopIteration as stop:
                del plans[slug]
                yield stop.value


def _stop(pool: ProcessPoolExecutor) -> None:
    """End now: a running search can take minutes and Ctrl+C would otherwise wait for it.
    ProcessPoolExecutor has no public kill before Python 3.14 (terminate_workers)."""
    for process in list(pool._processes.values()):
        process.kill()
    pool.shutdown(wait=False, cancel_futures=True)


def _load(gamedata: Path, dataset: str) -> None:
    """Never raises: a failing initializer breaks the pool and hides the reason."""
    global _data, _error
    try:
        _data = load(gamedata)
        if _data.meta.dataset_hash != dataset:
            _error = f"gamedata/ changed during the run ({dataset} -> {_data.meta.dataset_hash})"
    except Exception as error:
        _error = f"worker could not load gamedata/: {error}"


def _task(slug: str, task: Task, budget: int) -> tuple[Found, float]:
    if _error or _data is None:
        raise release.ReleaseError(_error or "worker started without its dataset")
    started = time.monotonic()
    found = run(_data, _data.weapon_by_slug[slug], task, budget)
    return found, time.monotonic() - started
