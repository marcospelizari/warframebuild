"""The Updates page data (U10, G90): one entry per release that changed something, newest
first, carried from release to release in `updates.json`."""

from pathlib import Path
from typing import Literal

from app.gamedata.changes import Change, EntryChange
from app.gamedata.models import IsoDate, Model

UPDATES = "updates.json"


class BuildChange(Model):
    """One build of a gun that changed: `build` is "recommended" or a faction name."""

    build: str
    removed: list[str]  # names: mods, exilus, arcane, Incarnon evolutions, bonus element
    added: list[str]
    kill_before: float | None  # average kill time, seconds
    kill_after: float | None


class GunChange(Model):
    slug: str
    name: str
    change: Change
    stats_changed: bool  # the gun's own entry changed
    builds: list[BuildChange]


class Update(Model):
    # game: DE/WFCD/wiki files changed; calculator: same game files, our rules or code changed
    kind: Literal["game", "calculator"]
    release: str
    date: IsoDate
    game_update: str | None
    summary: list[str]  # fixed sentences made from the data
    entries: list[EntryChange]  # mods, arcanes and perks; gun stats are in `guns`
    guns: list[GunChange]
    unavailable: list[str]  # parts that could not be compared, and why


class Updates(Model):
    updates: list[Update]  # newest first


def read_updates(release_dir: Path) -> Updates:
    """Empty for a release made before the Updates page."""
    path = release_dir / UPDATES
    if not path.exists():
        return Updates(updates=[])
    return Updates.model_validate_json(path.read_bytes())
