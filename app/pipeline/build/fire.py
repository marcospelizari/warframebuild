"""Fire data DE and WFCD lack (G10): reference/fire_overrides.json and the wiki weapon data
modules (no delay between shots, per-attack forced procs and burst values)."""

from dataclasses import dataclass
from typing import Any

from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError
from app.pipeline.sources.wiki_weapon_data import AttackData, WeaponData

FILE = "fire_overrides.json"
WEAPON_KEYS = {
    "name",
    "exclude",
    "no_reload",
    "reload_replaces_shot",
    "beam_ramp_start",
    "reload_time",
    "source",
    "verified",
}
FLAGS = ("no_reload", "reload_replaces_shot")
HELD = "HELD"  # DE trigger of continuous (beam) weapons
CHARGE = "CHARGE"


@dataclass(frozen=True)
class FireOverrides:
    weapons: dict[str, dict[str, Any]]
    beam_ramp_start: float  # default for every beam (saved Continuous_Weapon)

    @classmethod
    def load(cls, data: dict[str, Any]) -> "FireOverrides":
        default = data.get("defaults", {}).get("beam_ramp_start")
        if not isinstance(default, dict):
            raise RefreshError(f"reference/{FILE}: defaults.beam_ramp_start is required")
        require_verified(default, FILE, "defaults.beam_ramp_start")
        weapons = data.get("weapons", {})
        for uid, row in weapons.items():
            unknown = sorted(set(row) - WEAPON_KEYS)
            if unknown:
                raise RefreshError(f"reference/{FILE} {uid}: unknown keys {unknown}")
            require_verified(row, FILE, uid)
            for flag in FLAGS:
                if flag in row and not isinstance(row[flag], bool):
                    raise RefreshError(f"reference/{FILE} {uid}: {flag} must be true or false")
        return cls(weapons, _fraction(default.get("value"), "defaults.beam_ramp_start"))

    def excluded(self, uid: str) -> str | None:
        reason = self.weapons.get(uid, {}).get("exclude")
        return None if reason is None else str(reason)

    def check_known(self, gun_ids: set[str]) -> None:
        unknown = sorted(set(self.weapons) - gun_ids)
        if unknown:
            raise RefreshError(f"reference/{FILE}: unknown guns {unknown}")

    def no_reload(self, uid: str) -> bool:
        return self.weapons.get(uid, {}).get("no_reload", False) is True

    def reload_replaces_shot(self, uid: str) -> bool:
        return self.weapons.get(uid, {}).get("reload_replaces_shot", False) is True

    def reload_time(self, uid: str, de_value: float) -> float:
        value = self.weapons.get(uid, {}).get("reload_time", de_value)
        if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
            raise RefreshError(f"reference/{FILE} {uid}: reload_time must be a number >= 0")
        return float(value)

    def beam_start(self, uid: str, name: str, trigger: str) -> float | None:
        value = self.weapons.get(uid, {}).get("beam_ramp_start")
        if trigger != HELD:
            if value is not None:
                raise RefreshError(f"reference/{FILE} {name}: beam_ramp_start on a non-beam gun")
            return None
        return self.beam_ramp_start if value is None else _fraction(value, name)

    def attack_beam_start(
        self, uid: str, name: str, trigger: str, attack: AttackData | None
    ) -> float | None:
        """An attack's own Held trigger makes it a beam (Torid Incarnon); an own non-Held
        trigger makes it not one (Atomos Incarnon); without one it follows the gun."""
        held = attack.held if attack is not None else None
        if held is None:
            return self.beam_start(uid, name, trigger)
        if not held:
            return None
        value = self.weapons.get(uid, {}).get("beam_ramp_start")
        return self.beam_ramp_start if value is None else _fraction(value, name)


def fire_rate(d: dict[str, Any], data: WeaponData | None) -> float | None:
    """DE fire rate, or None when the wiki module says the charge alone sets the rate."""
    rate = d.get("fireRate")
    if isinstance(rate, int | float) and rate > 0:
        return float(rate)
    if data is not None and data.no_shot_delay and d.get("trigger") == CHARGE:
        return None
    raise RefreshError(
        f"{d['name']} ({d['uniqueName']}): no usable fire rate in DE and no 'no delay' "
        f"rule in the wiki module. Add an `exclude` entry with the reason to "
        f"reference/{FILE} until real values are known."
    )


def attack_data(
    name: str, attack_names: list[str], data: WeaponData | None
) -> dict[str, AttackData | None]:
    """Module values per WFCD attack; None for every attack of a gun the modules lack."""
    if data is None:
        return dict.fromkeys(attack_names)
    if sorted(attack_names) != sorted(data.attacks):
        raise RefreshError(
            f"{name}: WFCD attacks {sorted(attack_names)} differ from the wiki module "
            f"{sorted(data.attacks)}; check both before trusting forced procs"
        )
    return {n: data.attacks[n] for n in attack_names}


def _fraction(value: Any, where: str) -> float:
    if not isinstance(value, int | float) or not 0 <= value <= 1:
        raise RefreshError(f"reference/{FILE} {where}: beam_ramp_start must be within 0..1")
    return float(value)
