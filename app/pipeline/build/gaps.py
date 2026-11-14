"""New guns and arcanes with incomplete data are left out with a reason; ones the previous
dataset had still fail the refresh, so a broken source never empties the site (G90 U7/U8)."""

from dataclasses import dataclass

from app.gamedata.meta import Exclusion
from app.gamedata.store import GameData
from app.pipeline.errors import DataGap, RefreshError


@dataclass(frozen=True)
class Established:
    """uniqueNames the previous dataset built: these must build again."""

    weapons: set[str]
    arcanes: set[str]

    @classmethod
    def of(cls, previous: GameData | None) -> "Established | None":
        """None on a first run: every entry must build."""
        if previous is None:
            return None
        return cls(
            {w.unique_name for w in previous.weapons}, {a.unique_name for a in previous.arcanes}
        )


class Gaps:
    def __init__(self, established: set[str] | None) -> None:
        """`established`: uniqueNames of the previous dataset; None = all (first run)."""
        self._established = established
        self.excluded: list[Exclusion] = []

    def exclude(self, unique_name: str, name: str, gap: DataGap) -> None:
        """Leave a new entry out with the gap as reason; an established one fails."""
        if self._established is None or unique_name in self._established:
            raise RefreshError(f"{name}: {gap}") from gap
        self.excluded.append(
            Exclusion(unique_name=unique_name, name=name, reason=str(gap), pending=True)
        )

    @property
    def ids(self) -> set[str]:
        return {e.unique_name for e in self.excluded}
