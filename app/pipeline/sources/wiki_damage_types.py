"""Faction damage type modifiers from the saved `<Type>_Damage` wiki pages (T2).

Each page's DAMAGE EFFICACY quote lists lines like `'''{{text|green|x1.5}}''' damage to
Grineer`. Damage/Overview Table only marks them + / -, so the values come from here.
Wiki-derived: CC BY-NC-SA 3.0 (NOTICE).
"""

import re
from pathlib import Path

from app.domain.effects import DamageType
from app.pipeline.errors import RefreshError

SUFFIX = ".wikitext"
PAGES: dict[str, DamageType] = {f"{t.value.capitalize()}_Damage": t for t in DamageType}
_LINE = re.compile(
    r"^'''\{\{text\|(?P<colour>green|red)\|x(?P<value>\d+(?:\.\d+)?)\}\}''' damage to "
    r"(?P<faction>[A-Za-z][A-Za-z ]{0,40}?)(?:<br\s*/>)?\s*$"
)


def load(wiki_dir: Path) -> dict[str, dict[DamageType, float]]:
    """Faction (as the pages write it) -> damage type -> multiplier; unlisted types = 1."""
    out: dict[str, dict[DamageType, float]] = {}
    for stem, damage_type in PAGES.items():
        path = wiki_dir / f"{stem}{SUFFIX}"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = _LINE.match(line.strip())
            if m is None:
                continue
            value = float(m["value"])
            if (value > 1) != (m["colour"] == "green") or value == 1:
                raise RefreshError(f"{path.name}:{number}: colour does not match x{value}")
            row = out.setdefault(m["faction"], {})
            if damage_type in row:
                raise RefreshError(f"{path.name}:{number}: {m['faction']} listed twice")
            row[damage_type] = value
    return out
