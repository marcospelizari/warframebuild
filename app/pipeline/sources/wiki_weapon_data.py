"""Weapon data modules of the WARFRAME Wiki (`Module:Weapons/data/<slot>`), saved by hand (T2).

Read only for data DE and WFCD lack, per attack: forced procs (saved Status_Effect,
Forced Procs), burst count and delay (saved Fire_Rate), and per weapon: sniper minimum
combo and the highest zoom level's bonus (saved Sniper_Rifle), magazine size where DE gives
none (0 = no magazine), attacks with no delay between shots (`FireRate = math.huge`: Lanka,
saved Fire_Rate), `ExtraHeadshotDmg` per attack (saved Enemy_Body_Parts, Notes) and an
attack's own `Trigger` (beams in Incarnon Form only, saved Continuous_Weapon:47-71).
Keyed by `InternalName` = DE uniqueName; attack names equal WFCD's. Wiki-derived:
CC BY-NC-SA 3.0 (NOTICE).
"""

import math
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.domain.effects import DamageType
from app.domain.status import CrowdControl, ForcedProc
from app.pipeline.errors import RefreshError
from app.pipeline.sources.wiki_lua import LuaError, parse_module

MODULES = ("Module_Weapons_data_primary", "Module_Weapons_data_secondary")
SUFFIX = ".lua"

# Wiki proc names -> our types; an unknown name fails the refresh.
FORCED_PROCS: dict[str, ForcedProc] = {
    "Impact": DamageType.IMPACT,
    "Puncture": DamageType.PUNCTURE,
    "Slash": DamageType.SLASH,
    "Heat": DamageType.HEAT,
    "Cold": DamageType.COLD,
    "Electricity": DamageType.ELECTRICITY,
    "Toxin": DamageType.TOXIN,
    "Blast": DamageType.BLAST,
    "Radiation": DamageType.RADIATION,
    "Gas": DamageType.GAS,
    "Magnetic": DamageType.MAGNETIC,
    "Viral": DamageType.VIRAL,
    "Corrosive": DamageType.CORROSIVE,
    "Void": DamageType.VOID,
    "Tau": DamageType.TAU,
    "Knockdown": CrowdControl.KNOCKDOWN,
    "Lifted": CrowdControl.LIFTED,
    "Ragdoll": CrowdControl.RAGDOLL,
    "Stagger": CrowdControl.STAGGER,
    "Big Stagger": CrowdControl.BIG_STAGGER,
    "Blind": CrowdControl.BLIND,
    "Stun": CrowdControl.STUN,
}


@dataclass(frozen=True)
class AttackData:
    forced_procs: list[ForcedProc]
    burst_count: int | None
    burst_delay: float | None
    no_shot_delay: bool  # FireRate = math.huge
    ammo_cost: float | None  # ammo per shot (0.5 per beam tick, 0 = none); None = not listed
    multishot: float | None = None  # projectiles per shot; None = not listed
    extra_headshot: float | None = None  # -2 = 1x heads; > 0 = extra headshot factor
    held: bool | None = None  # own Trigger is Held (a beam); None = no own Trigger
    parent: str | None = None  # AttackParentIndex: the attack this one is part of (a blast)


@dataclass(frozen=True)
class WeaponData:
    name: str
    attacks: dict[str, AttackData]  # by attack name
    sniper_combo_min: int | None
    magazine: int | None = None  # `Magazine`, 0 = no magazine; None = not listed
    zoom: list[str] | None = None  # highest zoom level's bonus lines ("+60% Headshot Damage")

    @property
    def no_shot_delay(self) -> bool:
        """Every attack fires again as soon as it is charged (Lanka)."""
        return bool(self.attacks) and all(a.no_shot_delay for a in self.attacks.values())


def load(wiki_dir: Path) -> dict[str, WeaponData]:
    out: dict[str, WeaponData] = {}
    for stem in MODULES:
        path = wiki_dir / f"{stem}{SUFFIX}"
        try:
            module = parse_module(path.read_text(encoding="utf-8"))
        except LuaError as error:
            raise RefreshError(f"{path.name}: {error}") from error
        if module == []:  # `{}`: Lua cannot tell an empty list from an empty table
            module = {}
        if not isinstance(module, dict):
            raise RefreshError(f"{path.name}: expected a table of weapons")
        for key, entry in module.items():
            weapon = _weapon(f"{path.name} {key}", entry)
            if weapon is None:
                continue
            unique_name, data = weapon
            if unique_name in out:
                raise RefreshError(f"{path.name} {key}: InternalName listed twice")
            out[unique_name] = data
    return out


def _weapon(where: str, entry: Any) -> tuple[str, WeaponData] | None:
    if not isinstance(entry, dict):
        raise RefreshError(f"{where}: expected a table")
    if entry.get("_IgnoreEntry"):
        return None
    unique_name = entry.get("InternalName")
    if not isinstance(unique_name, str) or not unique_name:
        raise RefreshError(f"{where}: no InternalName")
    attacks: dict[str, AttackData] = {}
    listed = entry.get("Attacks") or []
    names = {a.get("AttackIndex"): a.get("AttackName") for a in listed if isinstance(a, dict)}
    for attack in listed:
        if not isinstance(attack, dict) or not isinstance(attack.get("AttackName"), str):
            raise RefreshError(f"{where}: attack without AttackName")
        name = attack["AttackName"]
        if name in attacks:
            raise RefreshError(f"{where}: attack {name!r} listed twice")
        parent = attack.get("AttackParentIndex")
        if parent is not None and not isinstance(names.get(parent), str):
            raise RefreshError(f"{where} / {name}: AttackParentIndex {parent!r} names no attack")
        attacks[name] = replace(_attack(f"{where} / {name}", attack), parent=names.get(parent))
    combo = entry.get("SniperComboMin")
    if combo is not None and (not isinstance(combo, int) or combo < 1):
        raise RefreshError(f"{where}: SniperComboMin must be a positive integer")
    magazine = entry.get("Magazine")
    if magazine is not None and (not isinstance(magazine, int) or magazine < 0):
        raise RefreshError(f"{where}: Magazine must be an integer >= 0")
    return unique_name, WeaponData(
        str(entry.get("Name", "")), attacks, combo, magazine, _zoom(where, entry.get("Zoom"))
    )


_ZOOM_BONUS = re.compile(r"\((?P<bonus>[^()]{1,120})\)\s*$")


def _zoom(where: str, zoom: Any) -> list[str] | None:
    """Bonus lines of the last (highest) zoom level: "6x (+60% Headshot Damage)"."""
    if zoom is None:
        return None
    if not isinstance(zoom, list) or not all(isinstance(z, str) for z in zoom):
        raise RefreshError(f"{where}: Zoom must be a list of strings")
    match = _ZOOM_BONUS.search(zoom[-1]) if zoom else None
    return [b.strip() for b in match["bonus"].split(",")] if match else None


def _attack(where: str, a: dict[str, Any]) -> AttackData:
    procs = a.get("ForcedProcs") or []
    if not isinstance(procs, list):
        raise RefreshError(f"{where}: ForcedProcs is not a list")
    unknown = [p for p in procs if p not in FORCED_PROCS]
    if unknown:
        raise RefreshError(f"{where}: unknown forced procs {unknown}")
    count = a.get("BurstCount")
    delay = a.get("BurstDelay")
    if count is not None and (not isinstance(count, int) or count < 1):
        raise RefreshError(f"{where}: BurstCount must be a positive integer")
    if delay is not None and (not isinstance(delay, int | float) or not 0 <= delay < math.inf):
        raise RefreshError(f"{where}: BurstDelay must be a finite number >= 0")
    return AttackData(
        forced_procs=[FORCED_PROCS[p] for p in procs],
        burst_count=count,
        burst_delay=float(delay) if delay is not None else None,
        no_shot_delay=a.get("FireRate") == math.inf,
        ammo_cost=_ammo_cost(where, a),
        multishot=_multishot(where, a),
        extra_headshot=_extra_headshot(where, a),
        held=_held(where, a),
    )


def _held(where: str, a: dict[str, Any]) -> bool | None:
    """Incarnon Forms carry their own Trigger (Torid's is Held; Atomos's is Semi-Auto)."""
    trigger = a.get("Trigger")
    if trigger is None:
        return None
    if not isinstance(trigger, str) or not trigger:
        raise RefreshError(f"{where}: Trigger must be a string")
    return trigger == "Held"


def _extra_headshot(where: str, a: dict[str, Any]) -> float | None:
    value = a.get("ExtraHeadshotDmg")
    if value is None:
        return None
    if not isinstance(value, int | float) or not (value == -2 or 0 < value < math.inf):
        raise RefreshError(f"{where}: ExtraHeadshotDmg must be -2 or a number > 0")
    return float(value)


def _multishot(where: str, a: dict[str, Any]) -> float | None:
    value = a.get("Multishot")
    if value is None:
        return None
    if not isinstance(value, int | float) or not 0 < value < math.inf:
        raise RefreshError(f"{where}: Multishot must be a finite number > 0")
    return float(value)


def _ammo_cost(where: str, a: dict[str, Any]) -> float | None:
    # One module entry spells the key `Ammocost`.
    cost = a.get("AmmoCost", a.get("Ammocost"))
    if cost is None:
        return None
    if not isinstance(cost, int | float) or not 0 <= cost < math.inf:
        raise RefreshError(f"{where}: AmmoCost must be a finite number >= 0")
    return float(cost)
