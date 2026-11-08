"""warframe-public-export-plus (MIT; Calamity, Inc. and AMelonInsideLemon), Q41/T1.

Saved by hand into cache/raw/export-plus/, like wiki pages: never fetched by script.
Read only for fields the DE Public Export lacks: mod and weapon compatibility tags
(stored as given; what they mean for mod eligibility is decided in step 8) and the
starter-mod flag (a guard on reference/mod_filter.json). Keyed by DE uniqueName.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.pipeline.errors import RefreshError
from app.pipeline.sources import SourceFile, load_json, saved_date, sha256_16

REPO_URL = "https://github.com/calamity-inc/warframe-public-export-plus"
RAW_URL = "https://raw.githubusercontent.com/calamity-inc/warframe-public-export-plus/senpai"
DIR = "export-plus"
UPGRADES = "ExportUpgrades.json"
WEAPONS = "ExportWeapons.json"
FILES = (UPGRADES, WEAPONS)


class MissingExportPlus(RuntimeError):
    pass


@dataclass(frozen=True)
class ModTags:
    compatibility: list[str]
    incompatibility: list[str]


@dataclass(frozen=True)
class ExportPlus:
    weapon_tags: dict[str, list[str]]  # uniqueName -> compatibilityTags
    mod_tags: dict[str, ModTags]
    starter_mods: frozenset[str]  # isStarter: low-rank starter copies


def scan(raw_dir: Path) -> list[SourceFile]:
    """Record the saved files; fail with the save hint when one is missing."""
    missing = [n for n in FILES if not (raw_dir / DIR / n).is_file()]
    if missing:
        hint = "\n".join(f"  {RAW_URL}/{n} -> {raw_dir / DIR / n}" for n in missing)
        raise MissingExportPlus(f"save these export-plus files by browser:\n{hint}")
    return [
        SourceFile(f"{DIR}/{n}", f"{RAW_URL}/{n}", saved_date(p), sha256_16(p.read_bytes()))
        for n, p in ((n, raw_dir / DIR / n) for n in FILES)
    ]


def load(raw_dir: Path) -> ExportPlus:
    upgrades = _entries(load_json(raw_dir / DIR / UPGRADES), UPGRADES)
    weapons = _entries(load_json(raw_dir / DIR / WEAPONS), WEAPONS)
    return ExportPlus(
        weapon_tags={u: _tags(w, "compatibilityTags", u) for u, w in weapons.items()},
        mod_tags={
            u: ModTags(_tags(m, "compatibilityTags", u), _tags(m, "incompatibilityTags", u))
            for u, m in upgrades.items()
        },
        starter_mods=frozenset(u for u, m in upgrades.items() if m.get("isStarter") is True),
    )


def _entries(data: Any, name: str) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        raise RefreshError(f"export-plus {name}: format changed (expected uniqueName -> object)")
    return data


def _tags(entry: dict[str, Any], key: str, unique_name: str) -> list[str]:
    """A missing key means no tags; anything but a list of strings fails the refresh."""
    tags = entry.get(key, [])
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise RefreshError(f"export-plus {unique_name}: `{key}` is not a list of strings")
    return sorted(tags)
