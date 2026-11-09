"""Enemy data modules of the WARFRAME Wiki (`Module:Enemies/data/<faction>`), saved by hand (T2).

Read for base health, shield, armor, base level, faction and Overguard per enemy, keyed by
`InternalName` (DE uniqueName). Names repeat across modules, and some entries have no or a
repeated InternalName: such ids are ambiguous and cannot be used. The modules carry a few
Lua slips (repeated keys, stray positional values), read with Lua's own rules.
Wiki-derived: CC BY-NC-SA 3.0 (NOTICE).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.pipeline.errors import RefreshError
from app.pipeline.sources.wiki_lua import LuaError, parse_module

FACTIONS = (
    "anarchs",
    "corpus",
    "grineer",
    "infestation",
    "narmer",
    "orokin",
    "scaldra",
    "sentient",
    "stalker",
    "techrot",
    "themurmur",
    "unaffiliated",
)  # Module:Enemies/data/<faction>; all are read since ids may sit in any of them
MODULES = tuple(f"Module_Enemies_{f}" for f in FACTIONS)
SUFFIX = ".lua"
PLACEHOLDER = "[Wiki Dummy]"  # wiki test entry sharing Heavy Gunner's id


@dataclass(frozen=True)
class EnemyData:
    name: str
    module: str  # file stem
    faction: str  # as the module writes it ("Orokin" for Corrupted)
    health: float
    shield: float
    armor: float
    base_level: int
    overguard: float
    problem: str | None = None  # malformed stat; fails only if a reference row uses it


def load(wiki_dir: Path) -> dict[str, list[EnemyData]]:
    """InternalName -> entries (more than one = ambiguous)."""
    out: dict[str, list[EnemyData]] = {}
    for stem in MODULES:
        path = wiki_dir / f"{stem}{SUFFIX}"
        try:
            module = parse_module(path.read_text(encoding="utf-8"), lua_rules=True)
        except LuaError as error:
            raise RefreshError(f"{path.name}: {error}") from error
        if module == []:
            module = {}  # `return {}`
        if not isinstance(module, dict):
            raise RefreshError(f"{path.name}: expected a table of enemies")
        for name, entry in module.items():
            if name == PLACEHOLDER:
                continue
            enemy = _enemy(path.stem, str(name), entry)
            if enemy is not None:
                out.setdefault(enemy[0], []).append(enemy[1])
    return out


def _enemy(module: str, name: str, entry: Any) -> tuple[str, EnemyData] | None:
    general = entry.get("General") if isinstance(entry, dict) else None
    stats = entry.get("Stats") if isinstance(entry, dict) else None
    if not isinstance(general, dict) or not isinstance(stats, dict):
        return None
    uid = general.get("InternalName")
    if not isinstance(uid, str) or not uid:
        return None
    problems: list[str] = []
    return uid, EnemyData(
        name=name,
        module=module,
        faction=str(general.get("Faction", "")),
        health=_number(stats, "Health", problems),
        shield=_number(stats, "Shield", problems),
        armor=_number(stats, "Armor", problems),
        base_level=int(_number(stats, "BaseLevel", problems, default=1)),
        overguard=_number(stats, "Overguard", problems),
        problem="; ".join(problems) or None,
    )


def _number(stats: dict[str, Any], key: str, problems: list[str], default: float = 0) -> float:
    value = stats.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        problems.append(f"`{key}` must be a number >= 0, got {value!r}")
        return 0.0
    return float(value)
