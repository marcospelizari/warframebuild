"""Incarnon perk text -> effects and the form it applies to (Q11, R6).

"Increase Base X by N" adds to the weapon's base value (`Operation.BASE`); other lines use
the mod parser. Notes that state a stacking rule keep the perk partial until reviewed.
"""

import re
from typing import Literal

from app.domain.effects import Effect, Operation, Parsed, Stat, Trigger
from app.parse.effects import parse
from app.parse.groups import header

Form = Literal["both", "normal", "incarnon"]

_BASE_STATS = {
    "damage": Stat.DAMAGE,
    "critical chance": Stat.CRITICAL_CHANCE,
    "critical damage multiplier": Stat.CRITICAL_DAMAGE,
    "status chance": Stat.STATUS_CHANCE,
    "magazine capacity": Stat.MAGAZINE_CAPACITY,
    "multishot": Stat.MULTISHOT,
}
_BASE = re.compile(
    r"Increased? Base (?P<stat>[A-Za-z ]+?) by \+?(?P<value>-?\d+(?:\.\d+)?)(?P<unit>%|x)?"
    r"(?: for (?P<dur>\d+(?:\.\d+)?)(?: seconds|s))?\.?"
    r"(?: Stacks up to (?P<stacks>\d+)x\.?)?",
    re.I,
)
_INCARNON_ONLY = re.compile(r"\s*for Incarnon Form\.?$", re.I)
_NORMAL_ONLY = re.compile(
    r"(does not (apply to|affect) (the )?Incarnon form|only affects untransformed)", re.I
)
_STACKING_NOTE = re.compile(r"\b(multiplicative|additive|flat value)\b", re.I)


def parse_perk(lines: list[str], notes: list[str]) -> tuple[Parsed, Form]:
    effects: list[Effect] = []
    unparsed: list[str] = []
    form: Form = "normal" if any(_NORMAL_ONLY.search(n) for n in notes + lines) else "both"
    for raw in lines:
        if _NORMAL_ONLY.search(raw):
            continue
        line = _INCARNON_ONLY.sub("", raw)
        if line != raw:
            form = "incarnon"
        found = _base(line)
        if found is None:
            p = parse([line])
            effects += p.effects
            unparsed += p.unparsed
        elif found:
            effects += found
        else:
            unparsed.append(line)
    unparsed += [n for n in notes if _STACKING_NOTE.search(n)]
    return Parsed(effects=effects, unparsed=unparsed), form


def _base(line: str) -> list[Effect] | None:
    """Effects of an "Increase Base X" line; [] = recognised but not modelled; None = other."""
    trigger: Trigger | None = Trigger.ALWAYS
    rest = line
    if (h := header(line)) is not None:
        trigger, rest = h[0], h[3]
    m = _BASE.fullmatch(rest.strip())
    if m is None:
        return None
    stat = _BASE_STATS.get(m["stat"].lower())
    if stat is None or trigger is None:
        return []
    value = float(m["value"]) / (100 if m["unit"] == "%" else 1)
    return [
        Effect(
            stat=stat,
            value=value,
            operation=Operation.BASE,
            trigger=trigger,
            duration_s=float(m["dur"]) if m["dur"] else None,
            max_stacks=int(m["stacks"]) if m["stacks"] else 1,
        )
    ]
