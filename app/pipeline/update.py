"""`wfb update` (G90 U12): refresh, then an incremental build-all, then what needs a person.

The full refresh report goes to a file; the terminal gets the patch summary, the build-all
result and the "needs you" list. The running app picks the new release up by itself (U11).
"""

from collections.abc import Callable

from app.optimize.search import MAX_EVALUATIONS
from app.pipeline import build_all, refresh


class UpdateError(RuntimeError):
    pass


def run(
    refresh_paths: refresh.Paths,
    build_paths: build_all.Paths,
    *,
    offline: bool = False,
    workers: int | None = None,
    budget: int = MAX_EVALUATIONS,
    progress: Callable[[str], None] = lambda _: None,
) -> list[str]:
    try:
        report = refresh.run(refresh_paths, offline=offline, fetch_images=not offline)
    except Exception as error:
        raise UpdateError(f"refresh failed, gamedata/ unchanged: {error}") from error
    full = refresh_paths.raw.parent / f"refresh-report-{report.meta.changed_on}.txt"
    full.write_text("\n".join(report.lines()) + "\n", encoding="utf-8")
    m = report.meta
    progress(f"refresh done: dataset {m.dataset_hash} ({m.game_update}); now build-all")
    try:
        built = build_all.run(build_paths, workers, budget, progress)
    except Exception as error:
        raise UpdateError(
            "build-all failed, current release unchanged (gamedata/ is already refreshed: "
            f"run `wfb build-all`): {error}"
        ) from error
    needs = report.needs_you()
    return [
        f"dataset {m.dataset_hash} ({m.game_update}, fetched {m.fetched})",
        *report.patch,
        f"full refresh report: {full}",
        *built,
        "needs you:" if needs else "needs you: nothing",
        *(f"  - {line}" for line in needs),
    ]
