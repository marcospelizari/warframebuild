"""Raw sources -> validated gamedata models. Reads files, returns models, writes nothing."""

from dataclasses import dataclass
from pathlib import Path

from app.domain.status_rules import StatusRules
from app.gamedata.models import (
    Arcane,
    Enemy,
    Exclusion,
    FactionModifiers,
    Incarnon,
    Join,
    Mod,
    ModSet,
    ReferenceHead,
    Weapon,
)
from app.pipeline.build import (
    arcanes,
    blasts,
    enemies,
    headshot,
    incarnon,
    mods,
    status_rules,
    weapon_classes,
    weapon_tags,
    weapons,
)
from app.pipeline.build.direct_bonus import DirectBonusTable
from app.pipeline.build.effects import Overrides, SwitchedOff
from app.pipeline.build.fire import FireOverrides
from app.pipeline.build.gaps import Established, Gaps
from app.pipeline.build.inputs import as_list, records, reference
from app.pipeline.errors import RefreshError
from app.pipeline.sources import (
    export_plus,
    load_json,
    wiki_damage_types,
    wiki_enemies,
    wiki_incarnon,
    wiki_local,
    wiki_progenitor,
    wiki_weapon_data,
)

__all__ = ["Dataset", "build"]


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
    incarnon: list[Incarnon]
    reference_head: ReferenceHead
    enemies: list[Enemy]
    factions: list[FactionModifiers]
    status_rules: StatusRules
    overrides_off: list[SwitchedOff]  # entry text changed since written (U2)
    excluded_arcanes: list[Exclusion]  # new arcanes with incomplete data (U8)
    blast_missing: list[str]  # guns with an AoE attack no wiki module links (G49)


def build(raw_dir: Path, reference_dir: Path, established: Established | None = None) -> Dataset:
    """`established` guns and arcanes must build; new ones with incomplete data are excluded
    with a reason (U7/U8). None: every entry must build."""
    gun_gaps = Gaps(established.weapons if established else None)
    arcane_gaps = Gaps(established.arcanes if established else None)
    de = raw_dir / "de"
    wfcd = [
        *as_list(load_json(raw_dir / "wfcd/Primary.json")),
        *as_list(load_json(raw_dir / "wfcd/Secondary.json")),
    ]
    wfcd_arcanes = as_list(load_json(raw_dir / "wfcd/Arcanes.json"))
    plus = export_plus.load(raw_dir)
    overrides = Overrides(reference(reference_dir / "overrides.json"))
    tag_rows = reference(reference_dir / weapon_tags.FILE)
    weapon_tags_all, weapon_parents = weapon_tags.fill(tag_rows, plus)
    manifest = records(load_json(de / "ExportManifest.json"), "Manifest")
    textures = {m["uniqueName"]: m.get("textureLocation") for m in manifest}
    gun_list, excluded, joins = weapons.build(
        records(load_json(de / "ExportWeapons_en.json"), "ExportWeapons"),
        wfcd,
        textures,
        FireOverrides.load(reference(reference_dir / "fire_overrides.json")),
        weapon_tags_all,
        wiki_weapon_data.load(raw_dir / "wiki"),
        DirectBonusTable.load(reference(reference_dir / "galvanized_behaviour.json")),
        wiki_progenitor.load(raw_dir / "wiki"),
        overrides,
        gun_gaps,
    )
    gun_list = weapon_classes.apply(
        reference(reference_dir / weapon_classes.FILE), gun_list, weapon_parents, gun_gaps
    )
    weapon_tags.check_known(
        tag_rows,
        {w.unique_name for w in gun_list} | {e.unique_name for e in excluded} | gun_gaps.ids,
    )
    mod_list, sets, denied = mods.build(
        load_json(de / "ExportUpgrades_en.json"),
        reference(reference_dir / "mod_filter.json"),
        overrides,
        reference(reference_dir / "mod_families.json"),
        reference(reference_dir / "exilus.json"),
        plus,
        textures,
    )
    arcane_list = arcanes.build(
        records(load_json(de / "ExportRelicArcane_en.json"), "ExportRelicArcane"),
        wfcd_arcanes,
        overrides,
        textures,
        arcane_gaps,
    )
    saved_pages = wiki_local.pages(reference_dir)
    perks = incarnon.build(
        wiki_incarnon.load(raw_dir / "wiki", wiki_incarnon.native_stems(saved_pages)),
        gun_list,
        overrides,
        reference(reference_dir / "main_attack.json"),
        gun_gaps,
    )
    gun_list = [w for w in gun_list if w.unique_name not in gun_gaps.ids]
    titles = {p.stem: p.title for p in saved_pages}
    gun_list, head = headshot.apply(
        reference(reference_dir / "headshot.json"),
        gun_list,
        {i.unique_name for i in perks},
        titles,
        gun_gaps.ids,
    )
    gun_list, blast_missing = blasts.apply(
        reference(reference_dir / blasts.FILE), gun_list, perks, gun_gaps.ids
    )
    enemy_list, factions = enemies.build(
        reference(reference_dir / "enemies.json"),
        reference(reference_dir / "enemy_scaling.json"),
        wiki_enemies.load(raw_dir / "wiki"),
        wiki_damage_types.load(raw_dir / "wiki"),
        (raw_dir / "wiki/Enemy_Body_Parts.wikitext").read_text(encoding="utf-8").splitlines(),
        titles,
    )
    rules = status_rules.build(reference(reference_dir / status_rules.FILE), titles)
    overrides.check_all_used(gun_gaps.ids | arcane_gaps.ids)
    _check_arcane_classes(arcane_list, gun_list)
    if not gun_list or not mod_list or not arcane_list:
        raise RefreshError(
            f"empty dataset: {len(gun_list)} weapons, {len(mod_list)} mods, "
            f"{len(arcane_list)} arcanes"
        )
    return Dataset(
        gun_list,
        sorted(excluded + gun_gaps.excluded, key=lambda e: e.unique_name),
        mod_list,
        sets,
        denied,
        arcane_list,
        joins,
        weapons.game_update(wfcd),
        perks,
        head,
        enemy_list,
        factions,
        rules,
        overrides.switched_off,
        arcane_gaps.excluded,
        blast_missing,
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
