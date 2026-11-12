"""What each entry shows (snapshot) and what changed since the previous dataset (U1, G90).

Both files sit beside the dataset, outside its hash. The snapshot has its own small format,
so the next refresh can compare against it even after a gamedata schema change.
"""

from enum import StrEnum
from pathlib import Path
from typing import Literal

from app.domain.effects import Support
from app.gamedata.models import Model

SNAPSHOT = "snapshot.json"
CHANGES = "changes.json"

_RANK = {Support.FULL: 0, Support.PARTIAL: 1, Support.UNSUPPORTED: 2}


class Kind(StrEnum):
    WEAPON = "weapon"
    MOD = "mod"
    ARCANE = "arcane"
    PERK = "perk"


class Shown(Model):
    """One entry as text: max-rank stat lines (mods, arcanes, perks) or stat fields (guns)."""

    kind: Kind
    name: str
    lines: list[str]
    support: Support | None  # None for guns
    unparsed: list[str]  # damage-related text not modelled


class Snapshot(Model):
    format: Literal[1] = 1
    entries: dict[str, Shown]  # uniqueName; perks `<gun uniqueName>#<perk name>`


class Change(StrEnum):
    NEW = "new"
    CHANGED = "changed"
    REMOVED = "removed"


class EntryChange(Model):
    key: str
    kind: Kind
    name: str
    change: Change
    before: list[str]  # [] for new entries
    after: list[str]  # [] for removed entries
    support_before: Support | None
    support_after: Support | None
    unparsed: list[str]  # after the change

    @property
    def support_dropped(self) -> bool:
        if self.support_before is None or self.support_after is None:
            return False
        return _RANK[self.support_after] > _RANK[self.support_before]


class Changes(Model):
    """Entry changes from dataset `from_hash` to `to_hash`."""

    from_hash: str | None  # None: first dataset, or no snapshot to compare with
    to_hash: str
    sources_changed: bool  # DE/WFCD/wiki files differ: a game update, not only our rules
    unavailable: str | None = None  # why no comparison was possible
    entries: list[EntryChange]


def read_snapshot(gamedata_dir: Path) -> Snapshot | None:
    """None when the dataset has no snapshot; ValueError when it is unreadable."""
    path = gamedata_dir / SNAPSHOT
    if not path.exists():
        return None
    return Snapshot.model_validate_json(path.read_bytes())


def read_changes(gamedata_dir: Path) -> Changes | None:
    path = gamedata_dir / CHANGES
    if not path.exists():
        return None
    return Changes.model_validate_json(path.read_bytes())
