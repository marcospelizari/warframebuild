"""`wfb fixtures`: trim cache/raw/ DE + WFCD data to a few weapons for tests/fixtures/raw/.

Wiki pages are never copied: saved copies stay private (G23); tests create stubs.
"""

import json
import shutil
from pathlib import Path
from typing import Any

from app.data.sources import load_json

WEAPONS = (
    "Braton Prime",  # Incarnon, AoE attack
    "Burston Prime",  # burst trigger
    "Cyanex",  # gas damage slot
    "Grimoire",  # slug collision (two entries)
    "Haalvu",  # tau damage slot
    "Kuva Hind",  # Kuva, burst
    "Laetum",  # native Incarnon
    "Lanka",  # fire rate 0 -> excluded by override
    "Lex Prime",  # secondary
    "Sirocco",  # Drifter weapon -> excluded by category
    "Sonicor",  # attacks differ from DE summary
    "Strun Wraith",  # shotgun, falloff
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
)
ARCANE_NAMES = ("Primary Merciless", "Secondary Deadhead", "Arcane Energize")


def write(raw_dir: Path, out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "de").mkdir(parents=True)
    (out_dir / "wfcd").mkdir()

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
