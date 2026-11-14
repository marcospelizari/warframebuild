"""`wfb sample`: a release of a few guns, made exactly like build-all, in minutes instead of
hours: to check a change before the full run and to work on the web app
(`wfb serve --sample`). It has its own folders; the real release is never touched."""

from collections.abc import Callable
from pathlib import Path

from app.optimize.search import MAX_EVALUATIONS
from app.pipeline import build_all, frozen_data

# The 5 primary and 5 secondary guns with the fastest Recommended kills in release
# db2e44fbdacf44d0 (the top of the G92 tier list).
GUNS = (
    "Perigale",
    "Phenmor",
    "Sybaris Prime",
    "Daikyu Prime",
    "Kuva Bramma",
    "Vasto",
    "Vasto Prime",
    "Laetum",
    "Sicarus Prime",
    "Ballistica Prime",
)


def paths(root: Path) -> build_all.Paths:
    """The sample's own gamedata copy (GUNS only) and releases folder under cache/sample/."""
    return build_all.Paths(
        root / "cache/sample/gamedata",
        root / "reference",
        root / "cache/sample/releases",
        root / "app",
    )


def run(
    gamedata: Path,
    sample: build_all.Paths,
    workers: int | None = None,
    budget: int = MAX_EVALUATIONS,
    progress: Callable[[str], None] = lambda _: None,
) -> list[str]:
    """Copy `gamedata` with only GUNS into `sample.gamedata`, then build-all on it; guns whose
    inputs did not change are copied from the previous sample release."""
    frozen_data.write(gamedata, sample.gamedata, GUNS)
    return build_all.run(sample, workers, budget, progress)
