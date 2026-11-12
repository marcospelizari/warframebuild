"""What the app serves, swapped as a whole when `wfb build-all` makes a new release (G90 U11).

A request reads `Served` once, so it never mixes the data of one release with the builds or
workers of another. The watcher loads a new release beside the old one and swaps it in;
the old workers finish their running jobs and stop. A release that fails to load is logged
once and the old one keeps serving.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, Request

from app.api import jobs
from app.api.runner import Runner
from app.gamedata.release import Release, current, open_current
from app.gamedata.store import GameData, load

INTERVAL_S = 5.0  # how often the `current` pointer is read (one small file)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Served:
    data: GameData
    release: Release | None  # None: no usable release, /builds answers 503
    runner: Runner
    builds_cache: dict[str, bytes] = field(default_factory=dict)  # this release's responses


@dataclass
class Pool:
    """How workers are made: processes load the release's folder, threads get the data."""

    size: int
    queue: int
    timeout: float
    processes: bool

    def runner(self, data: GameData, folder: Path) -> Runner:
        source: object = folder if self.processes else data
        return Runner(
            self.size, self.queue, self.timeout, self.processes, jobs.load_data, (source,)
        )


def served(request: Request) -> Served:
    value: Served = request.app.state.served
    return value


def swap(app: FastAPI) -> bool:
    """Serve the release `current` names if it is new and loads; True when swapped.
    Call on the event loop thread: `Runner` is not thread-safe (tests call it directly)."""
    new = load_next(app)
    if new is None:
        return False
    install(app, new)
    return True


def load_next(app: FastAPI) -> Served | None:
    """The new release, loaded (slow: run it off the event loop); None when there is none."""
    releases: Path = app.state.releases
    old: Served = app.state.served
    folder = current(releases)
    if folder is None or (old.release is not None and folder.name == old.release.id):
        return None
    if folder.name == app.state.failed_release:
        return None  # logged once; tried again when `current` changes
    try:
        release = open_current(releases)
        if release is None or release.folder != folder:
            return None  # `current` moved while reading: next round
        data = load(release.gamedata)
    except (OSError, ValueError, KeyError) as error:
        app.state.failed_release = folder.name
        log.warning("new release %s not served (%s): keeping the old one", folder.name, error)
        return None
    pool: Pool = app.state.pool
    return Served(data, release, pool.runner(data, release.gamedata))


def install(app: FastAPI, new: Served) -> None:
    """On the event loop: no request is between its runner check and its submit."""
    old: Served = app.state.served
    app.state.served = new
    app.state.failed_release = None
    old.runner.shutdown()  # running jobs finish; their requests still get their answer
    log.info("now serving release %s", new.release.id if new.release else "-")


async def watch(app: FastAPI) -> None:
    """Background task of the app's lifespan."""
    while True:
        await asyncio.sleep(INTERVAL_S)
        try:
            new = await asyncio.to_thread(load_next, app)
            if new is not None:
                install(app, new)
        except Exception:  # never end the watcher: the next round tries again
            log.exception("release check failed")
