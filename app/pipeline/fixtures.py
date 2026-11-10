"""`wfb fixtures`: trim cache/raw/ DE, WFCD and export-plus data for tests/fixtures/raw/.

Wiki pages are never copied: saved copies stay private (G23); tests create stubs.
"""

import json
import shutil
from pathlib import Path
from typing import Any

from app.pipeline.sources import export_plus, load_json

WEAPONS = (
    "Braton Prime",  # Incarnon, AoE attack
    "Burston Prime",  # burst trigger
    "Convectrix",  # beam with its own ramp-up start (fire_overrides.json)
    "Cyanex",  # gas damage slot
    "Embolist",  # beam with its own ramp-up start
    "Epitaph",  # no reload between shots; forced procs per attack
    "Epitaph Prime",  # no reload between shots (own page)
    "Grimoire",  # slug collision (two entries)
    "Haalvu",  # tau damage slot
    "Kuva Hind",  # Kuva, burst
    "Laetum",  # native Incarnon
    "Lanka",  # fire rate 0: no delay between shots (wiki module)
    "Lex Prime",  # secondary
    "Nataruk",  # bow; reload from the wiki module (fire_overrides.json)
    "Phage",  # beam with its own ramp-up start
    "Sirocco",  # Drifter weapon -> excluded by category
    "Sonicor",  # attacks differ from DE summary
    "Strun Wraith",  # shotgun, falloff
    "Vectis",  # reload replaces one shot interval
    "Vectis Prime",
)
MOD_NAMES = (
    "Serration",  # normal + beginner + intermediate
    "Split Chamber",  # normal + non-Primed Expert copy
    "Primed Cryo Rounds",  # Primed under /Expert/
    "Point Strike",
    "Vital Sense",
    "Hornet Strike",
    "Barrel Diffusion",
    "Galvanized Aptitude",
    "Hunter Munitions",
    "Vigilante Armaments",  # set member
    "Rifle Riven Mod",  # no levelStats
    "Comet Rounds",  # Conclave only
    "Double Tap",  # Conclave mod allowed: works outside Conclave
    "Semi-Rifle Cannonade",  # rules in DE description
    "Sniper Ammo Mutation",  # DE type `---`, category from compat name Sniper
    "Charged Chamber",  # typed PRIMARY mod with compat name Sniper
    "Primed Chamber",  # joined to Charged Chamber (mod_families.json)
    "Rifle Aptitude",  # joined to Galvanized Aptitude (mod_families.json)
    "Critical Delay",  # joined to Point Strike (mod_families.json)
    "Critical Deceleration",  # joined to Blunderbuss
    "Blunderbuss",
    "Creeping Bullseye",  # joined to Pistol Gambit
    "Pistol Gambit",
    "Mending Shot",  # joined to Thunderbolt (saved Mod/Compatibility)
    "Thunderbolt",
)
ARCANE_NAMES = (
    "Primary Merciless",
    "Secondary Deadhead",
    "Shotgun Vendetta",  # slot limited to shotguns
    "Arcane Energize",  # Warframe arcane, not a gun slot
)


def write(raw_dir: Path, out_dir: Path) -> None:
    """Build in a sibling staging folder; the old fixtures are replaced only on success."""
    staging = out_dir.with_name(f".{out_dir.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    try:
        _write(raw_dir, staging)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if out_dir.exists():
        shutil.rmtree(out_dir)
    staging.rename(out_dir)


def _write(raw_dir: Path, out_dir: Path) -> None:
    (out_dir / "de").mkdir(parents=True)
    (out_dir / "wfcd").mkdir()
    (out_dir / export_plus.DIR).mkdir()

    weapons = load_json(raw_dir / "de/ExportWeapons_en.json")
    assert isinstance(weapons, dict)
    de_weapons = _pick(weapons["ExportWeapons"], WEAPONS)
    ids = {w["uniqueName"] for w in de_weapons}
    _save(out_dir / "de/ExportWeapons_en.json", {"ExportWeapons": de_weapons})

    upgrades = load_json(raw_dir / "de/ExportUpgrades_en.json")
    assert isinstance(upgrades, dict)
    mods = _pick(upgrades["ExportUpgrades"], MOD_NAMES)
    sets = {m["modSet"] for m in mods if m.get("modSet")}
    _save(
        out_dir / "de/ExportUpgrades_en.json",
        {
            "ExportUpgrades": mods,
            "ExportModSet": [s for s in upgrades["ExportModSet"] if s["uniqueName"] in sets],
        },
    )

    arcanes = load_json(raw_dir / "de/ExportRelicArcane_en.json")
    assert isinstance(arcanes, dict)
    _save(
        out_dir / "de/ExportRelicArcane_en.json",
        {"ExportRelicArcane": _pick(arcanes["ExportRelicArcane"], ARCANE_NAMES)},
    )

    manifest = load_json(raw_dir / "de/ExportManifest.json")
    assert isinstance(manifest, dict)
    _save(
        out_dir / "de/ExportManifest.json",
        {"Manifest": [m for m in manifest["Manifest"] if m["uniqueName"] in ids]},
    )
    _save(out_dir / "de/ExportSentinels_en.json", {"ExportSentinels": []})
    shutil.copyfile(raw_dir / "de/index_en.txt.lzma", out_dir / "de/index_en.txt.lzma")

    for name in ("Primary.json", "Secondary.json"):
        data = load_json(raw_dir / "wfcd" / name)
        assert isinstance(data, list)
        _save(out_dir / "wfcd" / name, [w for w in data if w["uniqueName"] in ids])
    wfcd_arcanes = load_json(raw_dir / "wfcd/Arcanes.json")
    assert isinstance(wfcd_arcanes, list)
    _save(out_dir / "wfcd/Arcanes.json", _pick(wfcd_arcanes, ARCANE_NAMES))

    mod_ids = {m["uniqueName"] for m in mods}
    for name, keep in ((export_plus.WEAPONS, ids), (export_plus.UPGRADES, mod_ids)):
        data = load_json(raw_dir / export_plus.DIR / name)
        assert isinstance(data, dict)
        if name == export_plus.WEAPONS:
            keep = _with_parents(keep, data)
        _save(out_dir / export_plus.DIR / name, {u: e for u, e in data.items() if u in keep})


def _with_parents(ids: set[str], weapons: dict[str, Any]) -> set[str]:
    """The guns plus the export-plus entries of their parent chains (mod classes, G82)."""
    out = set(ids)
    for uid in ids:
        parent = weapons.get(uid, {}).get("parentName")
        while parent in weapons and parent not in out:
            out.add(parent)
            parent = weapons[parent].get("parentName")
    return out


def _pick(items: list[dict[str, Any]], names: tuple[str, ...]) -> list[dict[str, Any]]:
    picked = [i for i in items if i.get("name") in names]
    missing = set(names) - {i["name"] for i in picked}
    if missing:
        raise ValueError(f"fixture names not found: {sorted(missing)}")
    return picked


def _save(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
