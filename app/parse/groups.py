"""Stat strings -> groups of lines that share a trigger header ("On Kill:")."""

import re

from app.domain.effects import DamageType, Effect, Trigger
from app.parse.lines import STACKS, Context, stack_count

# Header lines ("On Kill:") -> trigger for the lines below them.
_HEADERS: dict[str, Trigger] = {
    "on hit": Trigger.ON_HIT,
    "on critical hit": Trigger.ON_CRIT,
    "on kill": Trigger.ON_KILL,
    "on headshot": Trigger.ON_HEADSHOT,
    "on headshot kill": Trigger.ON_HEADSHOT_KILL,
    "on weak point hit": Trigger.ON_WEAK_POINT_HIT,
    "on weakpoint hit": Trigger.ON_WEAK_POINT_HIT,
    "on consecutive weakpoint hits": Trigger.ON_WEAK_POINT_HIT,
    "on burst headshots": Trigger.ON_HEADSHOT,
    "on weak point kill": Trigger.ON_WEAK_POINT_KILL,
    "on reload": Trigger.ON_RELOAD,
    "on ability cast": Trigger.ON_ABILITY_CAST,
    "on melee kill": Trigger.ON_MELEE_KILL,
    "on status effect": Trigger.ON_STATUS,
}
# Any "<condition>: <text>" line is a header; an unknown condition is never modelled.
_HEADER = re.compile(
    r"(?P<head>[A-Za-z][A-Za-z0-9 ,.%'-]{2,60}?)\s?:\s?(?P<rest>.{0,300})", re.IGNORECASE
)
_STATUS_HEADER = re.compile(r"On (?:Weapon )?(?P<type>[A-Za-z]{3,12}) Status(?: Effect)?", re.I)


def dedupe(stats: list[str]) -> list[str]:
    """Arcanes repeat their passive lines: once inside the first string, once alone."""
    later = {s.strip() for s in stats[1:]}
    if not stats:
        return []
    first = [ln for ln in stats[0].split("\n") if ln.strip() not in later]
    return ["\n".join(first), *stats[1:]]


def groups(stats: list[str]) -> list[Context]:
    """Split into runs of lines that share a trigger header."""
    groups: list[Context] = []
    for text in stats:
        current = Context()
        groups.append(current)
        for raw in text.split("\n"):
            line = raw.strip()
            if not line:
                continue
            found = header(line)
            if found is None:
                current.lines.extend(sentences(line))
                continue
            current = Context(trigger=found[0], trigger_damage_type=found[1], head=found[2])
            groups.append(current)
            if found[3]:
                current.lines.extend(sentences(found[3]))
    return [g for g in groups if g.lines]


def header(line: str) -> tuple[Trigger | None, DamageType | None, str, str] | None:
    """(trigger or None when unknown, status type, header text, text after the colon)."""
    match = _HEADER.fullmatch(line)
    if not match:
        return None
    head, rest = match["head"].strip(), match["rest"].strip()
    if head.lower() in _HEADERS:
        return _HEADERS[head.lower()], None, head, rest
    status = _STATUS_HEADER.fullmatch(head)
    if status and status["type"].lower() in DamageType.__members__.values():
        return Trigger.ON_STATUS, DamageType(status["type"].lower()), head, rest
    return None, None, head, rest


def sentences(line: str) -> list[str]:
    """One stat per sentence, but keep "Stacks up to Nx." with the sentence before it."""
    parts = [p.strip() for p in re.split(r"(?<=\.)\s", line) if p.strip()]
    out: list[str] = []
    for part in parts:
        if out and STACKS.fullmatch(part):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


def spread_timing(effects: list[Effect], lines: list[str]) -> list[Effect]:
    """In a triggered group, one line may carry the duration/stacks for all of them
    (Split Flights: "+100% Multishot" then "-180% Accuracy for 2s. Stacks up to 4x.")."""
    if not effects or effects[0].trigger == Trigger.ALWAYS:
        return effects
    durations = {e.duration_s for e in effects if e.duration_s}
    text = " ".join(lines)
    dur_m = re.search(r" for (\d{1,3}(?:\.\d{1,2})?)s\b", text)
    stack_m = STACKS.search(text)
    duration = durations.pop() if len(durations) == 1 else (float(dur_m[1]) if dur_m else None)

    out = []
    for e in effects:
        update: dict[str, object] = {}
        if e.duration_s is None and duration is not None:
            update["duration_s"] = duration
        # A cap in % ("Stacks up to 480%") depends on each effect's own value.
        stacks = stack_count(stack_m, e.value) if stack_m else None
        if e.max_stacks == 1 and stacks:
            update["max_stacks"] = stacks
        out.append(e.model_copy(update=update) if update else e)
    return out
