"""Stat text -> effects (Q8/R2). Shared by mods, arcanes and set bonuses.

The text is cleaned DE stat text (app.data.build.common.clean_text). Every line
is either modelled, recognised as utility (no damage effect), or kept in
`unparsed` when it mentions something damage-related. Regexes are anchored with
bounded repeats only (S5): no nested quantifiers, input is one short line.
"""

import re
from dataclasses import dataclass, field

from app.domain.effects import (
    PHYSICAL_TYPES,
    DamageType,
    Effect,
    Faction,
    Operation,
    Parsed,
    Stat,
    Trigger,
)

_NUM = r"(?P<value>[+-]?\d{1,4}(?:\.\d{1,3})?)"

# Stat name in DE text -> (stat, damage_type). Longest names first in the regex.
_STATS: dict[str, tuple[Stat, DamageType | None]] = {
    "damage": (Stat.DAMAGE, None),
    "multishot": (Stat.MULTISHOT, None),
    "fire rate": (Stat.FIRE_RATE, None),
    "critical chance": (Stat.CRITICAL_CHANCE, None),
    "critical damage": (Stat.CRITICAL_DAMAGE, None),
    "status chance": (Stat.STATUS_CHANCE, None),
    "status duration": (Stat.STATUS_DURATION, None),
    "status damage": (Stat.STATUS_DAMAGE, None),
    "direct damage": (Stat.DIRECT_DAMAGE, None),
    "weak point damage": (Stat.WEAK_POINT_DAMAGE, None),
    "weak point critical chance": (Stat.WEAK_POINT_CRITICAL_CHANCE, None),
    "to headshot multiplier": (Stat.HEADSHOT_MULTIPLIER, None),
    "magazine capacity": (Stat.MAGAZINE_CAPACITY, None),
    "reload speed": (Stat.RELOAD_SPEED, None),
    "ammo efficiency": (Stat.AMMO_EFFICIENCY, None),
    **{t.value: (Stat.PHYSICAL if t in PHYSICAL_TYPES else Stat.ELEMENT, t) for t in DamageType},
}
_STAT_NAMES = "|".join(re.escape(n) for n in sorted(_STATS, key=len, reverse=True))

_ONE_STAT = rf"(?:{_STAT_NAMES})(?: damage)?"
# "+165% Damage", "-15% Damage", "+60% Fire Rate (x2 for Bows)",
# "+135% Critical Chance when Aiming for 9s", "+30% Damage for 4s. Stacks up to 12x.",
# one value for several stats: "+300% Gas Damage and Status Chance for 6s"
_SIMPLE = re.compile(
    rf"(?:Gain )?{_NUM}(?P<pct>%)? (?P<stats>{_ONE_STAT}(?: and {_ONE_STAT}){{0,3}})"
    r"(?P<bows> \(x2 for Bows\))?(?P<aim> when Aiming)?"
    r"(?: for (?P<dur>\d{1,3}(?:\.\d{1,2})?)s)?\.?"
    r"(?: Stacks up to (?:(?P<stacks>\d{1,3})x|(?P<cap>\d{1,4})%)\.?)?",
    re.IGNORECASE,
)
_FACTION = re.compile(
    r"x(?P<value>\d{1,2}(?:\.\d{1,3})?) Damage to (?:The )?(?P<faction>[A-Za-z]{3,20})",
    re.IGNORECASE,
)
_FIRST_SHOT = re.compile(rf"{_NUM}% Damage on first shot in Magazine", re.IGNORECASE)
_PROC_ON_CRIT = re.compile(
    rf"{_NUM}% chance to apply (?P<type>[A-Za-z]{{3,12}}) on Critical", re.IGNORECASE
)
_SET_CRIT_UPGRADE = re.compile(
    rf"{_NUM}% chance to enhance Critical Hits from (?:Primary|Secondary) Weapons\.?",
    re.IGNORECASE,
)
_LOCKED = re.compile(r"(?P<stat>Multishot|Fire Rate) cannot be modified\.?", re.IGNORECASE)
_REQUIRES = re.compile(r"Only compatible with (?P<trigger>Semi-Auto) Trigger\.?", re.IGNORECASE)
_TRIGGER_NAMES = {"semi-auto": "SEMI"}
# "Stacks up to 12x." or a cap on the total: "Stacks up to 480%." (12% per stack -> 40)
_STACKS = re.compile(r"Stacks up to (?:(?P<stacks>\d{1,3})x|(?P<cap>\d{1,4})%)\.?", re.IGNORECASE)

# Header lines ("On Kill:") -> trigger for the lines below them.
_HEADERS: dict[str, Trigger] = {
    "on hit": Trigger.ON_HIT,
    "on critical hit": Trigger.ON_CRIT,
    "on kill": Trigger.ON_KILL,
    "on headshot": Trigger.ON_HEADSHOT,
    "on headshot kill": Trigger.ON_HEADSHOT_KILL,
    "on weak point hit": Trigger.ON_WEAK_POINT_HIT,
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

# Utility: lines known to change no damage, sustained DPS or enemy defences. Only these
# are dropped; any other line the parser cannot model stays in `unparsed` (R6), so an
# unknown combat rule can never pass as fully supported.
_UTILITY_STATS = (
    r"Punch Through|Blast (?:Radius|Range)|Projectile Speed|Weapon Recoil|Accuracy|Zoom"
    r"|Beam Range|Movement Speed|Sprint Speed|Dodge Speed|Mobility|Ammo Maximum|Life Steal"
    r"|Heal Rate|Revive Speed|Combo Duration|Shield Recharge Delay|from Health Orbs"
    r"|Magazine Reloaded/s when Holstered|Aim Glide/Wall Latch Duration|Arcane Revive"
    r"|Energy Regen/s|Energy"
)
_UTILITY = re.compile(
    r"(?:and )?[+-]?\d{1,4}(?:\.\d{1,3})?(?:%|m|s)? (?:to )?(?:" + _UTILITY_STATS + r")"
    r"(?: (?:when|while) (?:Aiming|Aim Gliding|Airborne|Sliding|Crouching))?"
    r"(?: and [+-]?\d{1,4}%? (?:" + _UTILITY_STATS + r"))?(?: for \d{1,3}s)?\.?"
    r"(?: Stacks up to \d{1,3}x\.?)?"
    r"|Improves the Blast Radius of weapons with Radial Attacks\.?"
    r"|Reveals target on Minimap for \+?\d{1,3}s\.?"
    r"|Reduces the chance an enemy will hear gunfire by \d{1,3}%\.?"
    r"|Converts (?:Primary|Secondary) ammo pickups to \d{1,3}% of Ammo Pick Up\.?",
    re.IGNORECASE,
)


def _unmodelled(line: str) -> bool:
    return not _UTILITY.fullmatch(line)


@dataclass
class _Context:
    trigger: Trigger | None = Trigger.ALWAYS  # None: condition we do not model (`head`)
    head: str = ""
    trigger_damage_type: DamageType | None = None
    lines: list[str] = field(default_factory=list)


def parse(stats: list[str], description: str = "") -> Parsed:
    """Effects of one entry at one rank: its stat strings plus its description."""
    effects: list[Effect] = []
    unparsed: list[str] = []
    requires: str | None = None
    for group in _groups(_dedupe(stats)):
        group_effects: list[Effect] = []
        for line in group.lines:
            if group.trigger is None:
                # "On shotgun kill within 5m of target:" -> keep the text, model nothing.
                if _unmodelled(line):
                    unparsed.append(f"{group.head}: {line}")
                continue
            found = _line(line, group)
            if found is None:
                if _unmodelled(line):
                    unparsed.append(line)
            else:
                group_effects.extend(found)
        effects.extend(_spread_timing(group_effects, group.lines))
    for line in _sentences(description):
        req = _REQUIRES.fullmatch(line)
        if req:
            requires = _TRIGGER_NAMES[req["trigger"].lower()]
            continue
        found = _line(line, _Context())
        if found is not None:
            effects.extend(found)
        elif _unmodelled(line):
            unparsed.append(line)
    return Parsed(effects=effects, unparsed=unparsed, requires_trigger=requires)


def _dedupe(stats: list[str]) -> list[str]:
    """Arcanes repeat their passive lines: once inside the first string, once alone."""
    later = {s.strip() for s in stats[1:]}
    if not stats:
        return []
    first = [ln for ln in stats[0].split("\n") if ln.strip() not in later]
    return ["\n".join(first), *stats[1:]]


def _groups(stats: list[str]) -> list[_Context]:
    """Split into runs of lines that share a trigger header."""
    groups: list[_Context] = []
    for text in stats:
        current = _Context()
        groups.append(current)
        for raw in text.split("\n"):
            line = raw.strip()
            if not line:
                continue
            header = _header(line)
            if header is None:
                current.lines.extend(_sentences(line))
                continue
            current = _Context(trigger=header[0], trigger_damage_type=header[1], head=header[2])
            groups.append(current)
            if header[3]:
                current.lines.extend(_sentences(header[3]))
    return [g for g in groups if g.lines]


def _header(line: str) -> tuple[Trigger | None, DamageType | None, str, str] | None:
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


def _sentences(line: str) -> list[str]:
    """One stat per sentence, but keep "Stacks up to Nx." with the sentence before it."""
    parts = [p.strip() for p in re.split(r"(?<=\.)\s", line) if p.strip()]
    out: list[str] = []
    for part in parts:
        if out and _STACKS.fullmatch(part):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


def _line(line: str, ctx: _Context) -> list[Effect] | None:
    """Effects of one line, [] for nothing, None when not understood."""
    assert ctx.trigger is not None
    if m := _FACTION.fullmatch(line):
        if m["faction"].lower() not in Faction.__members__.values():
            return None  # new faction: unparsed, never full
        return [
            Effect(
                stat=Stat.FACTION_DAMAGE,
                value=float(m["value"]),
                operation=Operation.MULTIPLY,
                faction=Faction(m["faction"].lower()),
                trigger=ctx.trigger,
                trigger_damage_type=ctx.trigger_damage_type,
            )
        ]
    if m := _FIRST_SHOT.fullmatch(line):
        # Separate multiplier, not with Serration (saved Calculating_Bonuses: "2x damage
        # on first shot" in the multiplicative examples).
        return [
            Effect(
                stat=Stat.DAMAGE,
                value=1 + _pct(m["value"]),
                operation=Operation.MULTIPLY,
                trigger=Trigger.FIRST_SHOT,
            )
        ]
    if m := _PROC_ON_CRIT.fullmatch(line):
        name = m["type"].lower()
        if name not in DamageType.__members__.values():
            return None
        return [
            Effect(
                stat=Stat.FORCED_PROC,
                value=_pct(m["value"]),
                operation=Operation.ADD,
                damage_type=DamageType(name),
                trigger=Trigger.ON_CRIT,
            )
        ]
    if m := _SET_CRIT_UPGRADE.fullmatch(line):
        return [
            Effect(stat=Stat.CRIT_TIER_UPGRADE, value=_pct(m["value"]), operation=Operation.ADD)
        ]
    if m := _LOCKED.fullmatch(line):
        stat = Stat.MULTISHOT if m["stat"].lower() == "multishot" else Stat.FIRE_RATE
        return [Effect(stat=stat, value=0, operation=Operation.LOCK)]
    return _simple_list(line, ctx)


def _simple_list(line: str, ctx: _Context) -> list[Effect] | None:
    """ "+3% Critical Damage and +2.25% Multishot for 12s. Stacks up to 40x." -> 2 effects."""
    assert ctx.trigger is not None
    parts = re.split(r" and (?=[+-]\d)", line)
    if len(parts) > 3:
        return None
    matches = [_SIMPLE.fullmatch(p) for p in parts]
    if not all(matches):
        # A trailing "Multishot cannot be modified." style sentence was split earlier.
        return None
    last = matches[-1]
    assert last is not None
    effects = []
    for m in matches:
        assert m is not None
        if not m["pct"]:
            return None  # "+40 Magazine Capacity" style counts are not modelled
        value = _pct(m["value"])
        dur = m["dur"] or last["dur"]
        stacks = _stack_count(m, value) or _stack_count(last, value)
        for name in re.split(r" and ", m["stats"]):
            key = name.lower()
            stat, damage = _STATS.get(key) or _STATS[key.removesuffix(" damage")]
            aiming = bool(m["aim"] or last["aim"])
            # Damage only while aiming multiplies separately (saved Calculating_Bonuses:
            # Lasting Purity "1.6x damage on aiming" in the multiplicative examples).
            separate = stat == Stat.DAMAGE and aiming and ctx.trigger == Trigger.ALWAYS
            effects.append(
                Effect(
                    stat=stat,
                    value=1 + value if separate else value,
                    operation=Operation.MULTIPLY if separate else Operation.STACKING_MULTIPLY,
                    damage_type=damage,
                    while_aiming=aiming,
                    duration_s=float(dur) if dur else None,
                    max_stacks=stacks or 1,
                    class_values={"Bow": value * 2} if m["bows"] else {},
                    trigger=ctx.trigger,
                    trigger_damage_type=ctx.trigger_damage_type,
                )
            )
    return effects


def _spread_timing(effects: list[Effect], lines: list[str]) -> list[Effect]:
    """In a triggered group, one line may carry the duration/stacks for all of them
    (Split Flights: "+100% Multishot" then "-180% Accuracy for 2s. Stacks up to 4x.")."""
    if not effects or effects[0].trigger == Trigger.ALWAYS:
        return effects
    durations = {e.duration_s for e in effects if e.duration_s}
    text = " ".join(lines)
    dur_m = re.search(r" for (\d{1,3}(?:\.\d{1,2})?)s\b", text)
    stack_m = _STACKS.search(text)
    duration = durations.pop() if len(durations) == 1 else (float(dur_m[1]) if dur_m else None)
    stacks = _stack_count(stack_m, effects[0].value) if stack_m else None
    out = []
    for e in effects:
        update: dict[str, object] = {}
        if e.duration_s is None and duration is not None:
            update["duration_s"] = duration
        if e.max_stacks == 1 and stacks:
            update["max_stacks"] = stacks
        out.append(e.model_copy(update=update) if update else e)
    return out


def _stack_count(m: re.Match[str], value: float) -> int | None:
    """ "12x" -> 12; a total cap "480%" with 12% per stack -> 40."""
    if m["stacks"]:
        return int(m["stacks"])
    if m["cap"] and value:
        return max(1, round(_pct(m["cap"]) / abs(value)))
    return None


def _pct(text: str) -> float:
    return round(float(text) / 100, 6)
