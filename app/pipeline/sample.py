"""`wfb sample`: search a few guns exactly as build-all does and publish nothing, to check a
change in minutes before the full run. The guns are the frozen test guns (special cases)."""

import os
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from app.gamedata.builds import Build, WeaponBuilds
from app.gamedata.store import load
from app.optimize.search import MAX_EVALUATIONS
from app.pipeline import build_all
from app.pipeline.frozen_data import GUNS


def run(
    gamedata: Path,
    workers: int | None = None,
    budget: int = MAX_EVALUATIONS,
    progress: Callable[[str], None] = lambda _: None,
) -> list[str]:
    started = time.monotonic()
    data = load(gamedata)
    slugs = sorted(w.slug for w in data.weapons if w.name in GUNS)
    workers = workers or os.cpu_count() or 1
    progress(f"sample: {len(slugs)} guns, {workers} workers, budget {budget}; nothing is published")

    def report(results: Iterator[WeaponBuilds]) -> list[str]:
        lines = []
        for done, b in enumerate(results, 1):
            minutes = (time.monotonic() - started) / 60
            line = f"{done}/{len(slugs)} {b.slug} ({minutes:.1f} min): {_summary(b)}"
            progress(line)
            lines.append(line)
        return lines

    lines = build_all.search(gamedata, data.meta.dataset_hash, slugs, workers, budget, report)
    minutes = (time.monotonic() - started) / 60
    estimate = minutes * len(data.weapons) / max(len(slugs), 1) / 60
    return [
        *lines,
        f"sample: {len(slugs)} guns in {minutes:.1f} min; a full build-all of "
        f"{len(data.weapons)} guns takes about {estimate:.1f} h with the same workers",
    ]


def _summary(b: WeaponBuilds) -> str:
    v = b.variants[0]
    element = f"{v.element.value} bonus, " if v.element else ""
    return f"{element}Recommended {_build(v.recommended)}; {len(v.factions)} faction builds"


def _build(b: Build) -> str:
    forma = "does not fit" if b.forma is None else f"{b.forma.forma} forma"
    return f"{b.status}, {len([m for m in b.mods if m])} mods, {forma}"
