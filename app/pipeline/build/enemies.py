"""reference/enemies.json + enemy_scaling.json + saved wiki enemy modules -> enemies at the
scored level (Steel Path), and faction damage type modifiers (step 8a, R1/G1)."""

import re
from typing import Any

from pydantic import ValidationError

from app.domain.effects import DamageType, Faction
from app.domain.enemy_scaling import Curve, Scaling
from app.gamedata.models import Enemy, EnemyHead, FactionModifiers
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError
from app.pipeline.sources.wiki_enemies import EnemyData

FILE = "enemies.json"
SCALING = "enemy_scaling.json"
ROW_KEYS = {"name", "head", "body_parts_line", "body_parts_name", "toxin_bypasses_shield"}
HEAD_KEYS = {"part", "multiplier", "critical"}
_SPOT = re.compile(
    r"(?P<part>\"?[A-Za-z][A-Za-z \"]*?)[¹²³⁴⁵⁶⁷⁸⁹]*\s*\((?P<m>\d+(?:\.\d+)?)x\)(?P<marks>[*†]*)"
)


def build(
    table: dict[str, Any],
    scaling: dict[str, Any],
    modules: dict[str, list[EnemyData]],
    modifiers: dict[str, dict[DamageType, float]],
    body_parts: list[str],
    titles: dict[str, str],
) -> tuple[list[Enemy], list[FactionModifiers]]:
    """`body_parts`: lines of the saved Enemy_Body_Parts page; `titles`: saved stem -> title."""
    level = table.get("level")
    rows = table.get("enemies")
    if not isinstance(level, int) or level < 1 or not isinstance(rows, dict) or not rows:
        raise RefreshError(f"reference/{FILE}: needs `level` (int >= 1) and `enemies`")
    curves = _Curves(scaling)
    bane = _bane(table.get("bane"))
    out = []
    for uid, row in rows.items():
        data = _check_row(uid, row, modules, body_parts)
        if data.faction not in modifiers or data.faction not in bane:
            missing = "damage modifiers" if data.faction not in modifiers else "bane entry"
            raise RefreshError(f"reference/{FILE} {data.name}: no {missing} for {data.faction!r}")
        q = level - data.base_level
        try:
            out.append(
                Enemy(
                    unique_name=uid,
                    name=data.name,
                    faction=data.faction,
                    level=level,
                    health=curves.health(data, q),
                    shield=curves.shield(data, q),
                    armor=curves.armor(data, q),
                    head=EnemyHead(**row["head"]) if row["head"] else None,
                    bane=bane[data.faction],
                    toxin_bypasses_shield=row.get("toxin_bypasses_shield", True),
                    source=titles[data.module],
                )
            )
        except (ValidationError, KeyError) as error:
            raise RefreshError(f"reference/{FILE} {data.name}: {error}") from error
    factions = [FactionModifiers(faction=f, modifiers=modifiers[f]) for f in sorted(modifiers)]
    return sorted(out, key=lambda e: (e.faction, e.name)), factions


def _bane(table: Any) -> dict[str, Faction | None]:
    if not isinstance(table, dict):
        raise RefreshError(f"reference/{FILE}: needs `bane` (module faction -> mod faction)")
    try:
        return {k: Faction(v) if v is not None else None for k, v in table.items()}
    except ValueError as error:
        raise RefreshError(f"reference/{FILE} bane: {error}") from error


def _check_row(
    uid: str, row: Any, modules: dict[str, list[EnemyData]], body_parts: list[str]
) -> EnemyData:
    if not isinstance(row, dict):
        raise RefreshError(f"reference/{FILE} {uid}: expected an object")
    extra = sorted(row.keys() - ROW_KEYS - {"verified"})
    if extra or not {"name", "head", "body_parts_line"} <= row.keys():
        raise RefreshError(f"reference/{FILE} {uid}: keys must be {sorted(ROW_KEYS)}")
    require_verified(row, FILE, uid)
    entries = modules.get(uid, [])
    if len(entries) != 1:
        raise RefreshError(f"reference/{FILE} {uid}: {len(entries)} module entries, need 1")
    data = entries[0]
    if data.problem:
        raise RefreshError(f"{data.module} {data.name}: {data.problem}")
    if row["name"] != data.name:
        raise RefreshError(f"reference/{FILE} {uid}: name {row['name']!r} is {data.name!r}")
    if data.overguard:
        raise RefreshError(f"reference/{FILE} {data.name}: has Overguard, not modelled (V12)")
    _check_head(row, body_parts)
    return data


def _check_head(row: dict[str, Any], body_parts: list[str]) -> None:
    """The row's head must be the page line's weak point; no head = only non-headshot ones."""
    name, number = row["name"], row["body_parts_line"]
    listed = row.get("body_parts_name", name)
    line = (
        body_parts[number - 1] if isinstance(number, int) and 0 < number <= len(body_parts) else ""
    )
    cells = [c.strip() for c in line.split("||")]
    if not re.match(rf"\|\s*\{{\{{E\|{re.escape(listed)}(\||\}}\}})", line) or len(cells) < 3:
        raise RefreshError(f"reference/{FILE} {name}: Enemy_Body_Parts:{number} is not {listed}")
    spots = [m for m in _SPOT.finditer(cells[2].replace("<br>", " ")) if "†" not in m["marks"]]
    head = row["head"]
    if head is None:
        if spots:
            raise RefreshError(f"reference/{FILE} {name}: page lists a headshot spot")
        return
    if not isinstance(head, dict) or head.keys() != HEAD_KEYS:
        raise RefreshError(f"reference/{FILE} {name}: head needs {sorted(HEAD_KEYS)}")
    match = [m for m in spots if m["part"].replace('"', "").strip() == head["part"]]
    if not match:
        raise RefreshError(
            f"reference/{FILE} {name}: no headshot spot {head['part']!r} on the page"
        )
    page_head = (float(match[0]["m"]), "*" not in match[0]["marks"])
    if page_head != (head["multiplier"], head["critical"]):
        raise RefreshError(
            f"reference/{FILE} {name}: page gives (multiplier, critical) {page_head}"
        )


class _Curves:
    """Health and shield curves by faction, one armor curve; Steel Path on health and shield."""

    def __init__(self, data: dict[str, Any]) -> None:
        try:
            require_verified(data, SCALING, "file")
            lower, upper = data["transition"]["lower"], data["transition"]["upper"]
            self.health_by = self._by_faction(data["health"], lower, upper)
            self.shield_by = self._by_faction(data["shield"], lower, upper)
            armor = data["armor"]
            self.armor_curve = self._scaling(armor, lower, upper)
            self.armor_min, self.armor_cap = float(armor["minimum"]), float(armor["cap"])
            self.sp_health = float(data["steel_path"]["health"])
            self.sp_shield = float(data["steel_path"]["shield"])
        except (KeyError, TypeError, ValueError) as error:
            raise RefreshError(f"reference/{SCALING}: {error!r}") from error

    @staticmethod
    def _scaling(row: dict[str, Any], lower: float, upper: float) -> Scaling:
        return Scaling(Curve(*row["f1"]), Curve(*row["f2"]), lower, upper)

    def _by_faction(
        self, rows: list[dict[str, Any]], lower: float, upper: float
    ) -> dict[str, Scaling]:
        out: dict[str, Scaling] = {}
        for row in rows:
            for faction in row["factions"]:
                if faction in out:
                    raise ValueError(f"{faction} listed twice")
                out[faction] = self._scaling(row, lower, upper)
        return out

    def health(self, e: EnemyData, q: int) -> float:
        return self._pick(self.health_by, e, "health").value(e.health, q) * self.sp_health

    def shield(self, e: EnemyData, q: int) -> float:
        if not e.shield:
            return 0.0
        return self._pick(self.shield_by, e, "shield").value(e.shield, q) * self.sp_shield

    def armor(self, e: EnemyData, q: int) -> float:
        """Level-scaled armor is clamped to [minimum, cap] (Enemy_Level_Scaling, Armor)."""
        if not e.armor:
            return 0.0
        return min(max(self.armor_curve.value(e.armor, q), self.armor_min), self.armor_cap)

    @staticmethod
    def _pick(by: dict[str, Scaling], e: EnemyData, stat: str) -> Scaling:
        if e.faction not in by:
            raise RefreshError(f"reference/{SCALING}: no {stat} curve for {e.faction} ({e.name})")
        return by[e.faction]
