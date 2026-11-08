"""Raw sources -> validated gamedata models. Reads files, returns models, writes nothing."""

from dataclasses import dataclass
from pathlib import Path

from app.data.build import arcanes, mods, weapons
from app.data.build.common import RefreshError, as_list, clean_text, records, reference
from app.data.build.effects import Overrides
from app.data.models import Arcane, Exclusion, Join, Mod, ModSet, Weapon
from app.data.sources import load_json

__all__ = ["Dataset", "RefreshError", "build", "clean_text"]


@dataclass(frozen=True)
class Dataset:
    weapons: list[Weapon]
    excluded_weapons: list[Exclusion]
    mods: list[Mod]
    mod_sets: list[ModSet]
    denied_mods: dict[str, int]
    arcanes: list[Arcane]
    joins: list[Join]
    game_update: str | None


def build(raw_dir: Path, reference_dir: Path) -> Dataset:
    de = raw_dir / "de"
    wfcd = [
        *as_list(load_json(raw_dir / "wfcd/Primary.json")),
        *as_list(load_json(raw_dir / "wfcd/Secondary.json")),
    ]
    wfcd_arcanes = as_list(load_json(raw_dir / "wfcd/Arcanes.json"))
    gun_list, excluded, joins = weapons.build(
        records(load_json(de / "ExportWeapons_en.json"), "ExportWeapons"),
        wfcd,
        records(load_json(de / "ExportManifest.json"), "Manifest"),
        reference(reference_dir / "fire_overrides.json")["weapons"],
    )
    overrides = Overrides(reference(reference_dir / "overrides.json"))
    mod_list, sets, denied = mods.build(
        load_json(de / "ExportUpgrades_en.json"),
        reference(reference_dir / "mod_filter.json"),
        overrides,
    )
    arcane_list = arcanes.build(
        records(load_json(de / "ExportRelicArcane_en.json"), "ExportRelicArcane"),
        wfcd_arcanes,
        overrides,
    )
    overrides.check_all_used()
    _check_arcane_classes(arcane_list, gun_list)
    if not gun_list or not mod_list or not arcane_list:
        raise RefreshError(
            f"empty dataset: {len(gun_list)} weapons, {len(mod_list)} mods, "
            f"{len(arcane_list)} arcanes"
        )
    return Dataset(
        gun_list, excluded, mod_list, sets, denied, arcane_list, joins, weapons.game_update(wfcd)
    )


def _check_arcane_classes(arcane_list: list[Arcane], gun_list: list[Weapon]) -> None:
    """A class-limited arcane (Shotgun Vendetta) must fit at least one gun: the link is
    two WFCD strings, and a renamed class would otherwise fit nothing silently."""
    classes = {(w.category, w.weapon_type) for w in gun_list}
    unmatched = [
        f"{a.name} ({a.weapon_type})"
        for a in arcane_list
        if a.weapon_type is not None and (a.category, a.weapon_type) not in classes
    ]
    if unmatched:
        raise RefreshError(f"arcanes limited to a weapon type no gun has: {unmatched}")
