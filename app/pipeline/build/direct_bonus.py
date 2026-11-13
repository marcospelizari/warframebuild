"""reference/galvanized_behaviour.json: per-attack exceptions to the default Galvanized
behaviour (G56). Default from the WFCD shot type (`wfcd.SHOT_TYPE_DIRECT`)."""

from dataclasses import dataclass
from typing import Any

from app.domain.direct_bonus import DirectBonus
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError
from app.pipeline.sources.wfcd import SHOT_TYPE_DIRECT

FILE = "galvanized_behaviour.json"


@dataclass(frozen=True)
class DirectBonusTable:
    weapons: dict[str, dict[str, DirectBonus]]  # uniqueName -> attack name -> behaviour

    @classmethod
    def load(cls, data: dict[str, Any]) -> "DirectBonusTable":
        weapons: dict[str, dict[str, DirectBonus]] = {}
        for uid, row in data.get("weapons", {}).items():
            require_verified(row, FILE, uid)
            attacks = row.get("attacks")
            if not isinstance(attacks, dict) or not attacks:
                raise RefreshError(f"reference/{FILE} {uid}: `attacks` must list attacks")
            try:
                weapons[uid] = {name: DirectBonus(v) for name, v in attacks.items()}
            except ValueError as error:
                raise RefreshError(f"reference/{FILE} {uid}: {error}") from error
        return cls(weapons)

    def check(self, attack_names: dict[str, list[str]], excluded: set[str]) -> None:
        """Every row names a gun in the data and attacks that gun has; rows of `excluded`
        guns wait until they are built."""
        for uid, attacks in self.weapons.items():
            if uid in excluded:
                continue
            if uid not in attack_names:
                raise RefreshError(f"reference/{FILE}: unknown gun {uid}")
            missing = sorted(set(attacks) - set(attack_names[uid]))
            if missing:
                raise RefreshError(f"reference/{FILE} {uid}: unknown attacks {missing}")

    def behaviour(self, uid: str, attack: str, shot_type: str | None) -> DirectBonus:
        row = self.weapons.get(uid, {})
        if attack in row:
            return row[attack]
        if shot_type not in SHOT_TYPE_DIRECT:
            raise RefreshError(f"unknown WFCD shot_type {shot_type!r} ({uid} / {attack})")
        return SHOT_TYPE_DIRECT[shot_type]
