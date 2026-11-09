"""Step 4.5 performance spike (#19): evaluations per second, plain Python vs numpy.

    uv run --with numpy python -m bench.run_spike            # full run (~30 s)
    uv run --with numpy python -m bench.run_spike --quick    # smoke run

One evaluation = one candidate (8 mods) scored against the enemies: the real domain hit
(`workload.shot_model`) plus the combat timeline and fights. Results are printed as
Markdown for bench/README.md.
"""

import argparse
import math
import os
import platform
import statistics
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData
from bench import evaluate_np, evaluate_py
from bench.timeline import events
from bench.workload import (
    ENEMIES,
    WEAPONS,
    Enemy,
    ShotModel,
    candidates,
    enemies,
    gamedata,
    pool,
    shot_model,
)

_DATA: GameData | None = None


def _data() -> GameData:
    global _DATA
    if _DATA is None:
        _DATA = gamedata()
    return _DATA


def setup(name: str, count: int) -> tuple[Weapon, list[list[Mod]], list[ShotModel], list[Enemy]]:
    data = _data()
    weapon = next(w for w in data.weapons if w.name == name)
    sets = candidates(pool(data, weapon), count, seed=7)
    models = [shot_model(weapon, s) for s in sets]
    foes = enemies(statistics.median(m.burst_dps for m in models), seed=11)
    return weapon, sets, models, foes


def per_call(fn: Callable[[], object], calls: int) -> float:
    """Seconds per call, best of 3 runs of `calls` calls."""
    best = math.inf
    for _ in range(3):
        start = time.perf_counter()
        for _ in range(calls):
            fn()
        best = min(best, (time.perf_counter() - start) / calls)
    return best


def _work(args: tuple[str, int, int]) -> int:
    """Pool job: full evaluation (hit + numpy fights) of `count` candidates."""
    name, count, seed = args
    data = _data()
    weapon = next(w for w in data.weapons if w.name == name)
    sets = candidates(pool(data, weapon), count, seed)
    models = [shot_model(weapon, s) for s in sets]
    foes = enemies(statistics.median(m.burst_dps for m in models), seed=11)
    for m in models:
        evaluate_np.score(m, foes)
    return count


def parallel_rate(workers: int, jobs: int, per_job: int) -> float:
    with ProcessPoolExecutor(max_workers=workers, initializer=_data) as ex:
        list(ex.map(_work, [(WEAPONS[0], 2, 1)] * workers))  # warm up every worker
        start = time.perf_counter()
        done = sum(ex.map(_work, [(WEAPONS[i % len(WEAPONS)], per_job, i) for i in range(jobs)]))
        return done / (time.perf_counter() - start)


def check_equal(models: Sequence[ShotModel], foes: Sequence[Enemy]) -> float:
    """Largest relative difference between the two evaluators' per-enemy costs."""
    worst = 0.0
    for m in models:
        a = evaluate_py.costs(m, foes)
        b = evaluate_np.costs(m, foes)
        worst = max(worst, max(abs(x - y) / x for x, y in zip(a, b, strict=True)))
    return worst


def measure(name: str, count: int) -> tuple[float, float, float]:
    """Print one table row; return seconds per candidate: hit, Python fights, numpy fights."""
    weapon, sets, models, foes = setup(name, count)

    def hits() -> None:
        for s in sets:
            shot_model(weapon, s)

    def run(
        evaluate: Callable[[ShotModel, Sequence[Enemy]], float],
        ms: Sequence[ShotModel],
        foes_: Sequence[Enemy],
    ) -> Callable[[], None]:
        def go() -> None:
            for m in ms:
                evaluate(m, foes_)

        return go

    hit_s = per_call(hits, 1) / len(sets)
    py16 = per_call(run(evaluate_py.score, models, foes), 1) / len(models)
    py2 = per_call(run(evaluate_py.score, models, foes[:2]), 1) / len(models)
    np16 = per_call(run(evaluate_np.score, models, foes), 1) / len(models)
    np2 = per_call(run(evaluate_np.score, models, foes[:2]), 1) / len(models)
    diff = check_equal(models[: min(50, count)], foes)
    ev = statistics.mean(len(events(m)[1]) for m in models)
    killed = statistics.mean(sum(c < 10 for c in evaluate_np.costs(m, foes)) for m in models)
    print(
        f"| {name} | {1 / models[0].interval:.1f} | {ev:.0f} | {killed:.1f}/16 "
        f"| {hit_s * 1e6:.0f} | {py16 * 1e3:.2f} / {py2 * 1e3:.2f} "
        f"| {np16 * 1e3:.3f} / {np2 * 1e3:.3f} | {diff:.1e} |"
    )
    return hit_s, py16, np16


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    quick = parser.parse_args().quick
    count = 20 if quick else 200
    print(f"CPU: {platform.processor() or platform.machine()}, {os.cpu_count()} threads")
    print(f"Python {platform.python_version()}, numpy {np.__version__}, enemies {ENEMIES}\n")
    print(
        "| Weapon | shots/s | events | killed | hit µs | Python ms (16 / 2 en.) "
        "| numpy ms (16 / 2 en.) | max rel diff |"
    )
    print("|---|---|---|---|---|---|---|---|")
    rows = [measure(name, count) for name in WEAPONS]
    hit = statistics.mean(r[0] for r in rows)
    py = statistics.mean(r[1] for r in rows)
    vec = statistics.mean(r[2] for r in rows)
    print(f"\nMean per evaluation (16 enemies): Python {1 / (hit + py):.0f}/s, ", end="")
    print(f"numpy {1 / (hit + vec):.0f}/s on one core (hit included)")
    jobs, per_job = (12, 20) if quick else (48, 200)
    for workers in (1, 6, 12):
        print(f"Parallel numpy, {workers} processes: {parallel_rate(workers, jobs, per_job):.0f}/s")


if __name__ == "__main__":
    main()
