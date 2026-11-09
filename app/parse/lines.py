"""One line of stat text -> effects: the stat vocabulary and line patterns (S5: anchored,
bounded repeats only, input is one short line)."""

import re
from dataclasses import dataclass, field

from app.domain.effects import (
    PHYSICAL_TYPES,
    DamageType,
    Effect,
    Faction,
    FireRateBoost,
    Operation,
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
    "critical multiplier": (Stat.CRITICAL_DAMAGE, None),  # wiki module zoom text
    "status chance": (Stat.STATUS_CHANCE, None),
    "status duration": (Stat.STATUS_DURATION, None),
    "status damage": (Stat.STATUS_DAMAGE, None),
    "direct damage": (Stat.DIRECT_DAMAGE, None),
    "weak point damage": (Stat.WEAK_POINT_DAMAGE, None),
    "weak point critical chance": (Stat.WEAK_POINT_CRITICAL_CHANCE, None),
    "to headshot multiplier": (Stat.HEADSHOT_MULTIPLIER, None),
    # "+100% Headshot Damage" (Deadhead perks) adds to the same pool (saved Incarnon_Evolutions,
    # Vectis Deadhead note: additive with Target Acquired and the scope bonus).
    "headshot damage": (Stat.HEADSHOT_MULTIPLIER, None),
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
# "Impact Status Effects have 35% chance to apply a Slash Status Effect (x2 when Fire Rate
# is below 2.5)" (Internal Bleeding, Hemorrhage)
_PROC_ON_STATUS = re.compile(
    rf"(?P<from>[A-Za-z]{{3,12}}) Status Effects have {_NUM}% chance to apply an? "
    r"(?P<type>[A-Za-z]{3,12}) Status Effect"
    r"(?: \(x(?P<factor>\d{1,2}) when Fire Rate is below (?P<below>\d{1,2}(?:\.\d{1,2})?)\))?\.?",
    re.IGNORECASE,
)
# Galvanized: "+40% Direct Damage per Status Type affecting the target for 20s. Stacks up
# to 2x." (under "On Kill:")
_PER_STATUS_TYPE = re.compile(
    rf"{_NUM}% Direct Damage per Status Type affecting the target"
    r"(?: for (?P<dur>\d{1,3}(?:\.\d{1,2})?)s)?\.?(?: Stacks up to (?P<stacks>\d{1,3})x\.?)?",
    re.IGNORECASE,
)
_SET_CRIT_UPGRADE = re.compile(
    rf"{_NUM}% chance to enhance Critical Hits from (?:Primary|Secondary) Weapons\.?",
    re.IGNORECASE,
)
_LOCKED = re.compile(r"(?P<stat>Multishot|Fire Rate) cannot be modified\.?", re.IGNORECASE)
REQUIRES = re.compile(r"Only compatible with (?P<trigger>Semi-Auto) Trigger\.?", re.IGNORECASE)
TRIGGER_NAMES = {"semi-auto": "SEMI"}
# "Stacks up to 12x." or a cap on the total: "Stacks up to 480%." (12% per stack -> 40)
STACKS = re.compile(r"Stacks up to (?:(?P<stacks>\d{1,3})x|(?P<cap>\d{1,4})%)\.?", re.IGNORECASE)


@dataclass
class Context:
    trigger: Trigger | None = Trigger.ALWAYS  # None: condition we do not model (`head`)
    head: str = ""
    trigger_damage_type: DamageType | None = None
    lines: list[str] = field(default_factory=list)


def line_effects(line: str, ctx: Context) -> list[Effect] | None:
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
    if m := _PROC_ON_STATUS.fullmatch(line):
        source, name = m["from"].lower(), m["type"].lower()
        types = DamageType.__members__.values()
        if source not in types or name not in types:
            return None
        boost = (
            FireRateBoost(below=float(m["below"]), factor=float(m["factor"]))
            if m["below"]
            else None
        )
        return [
            Effect(
                stat=Stat.FORCED_PROC,
                value=_pct(m["value"]),
                operation=Operation.ADD,
                damage_type=DamageType(name),
                trigger=Trigger.ON_STATUS,
                trigger_damage_type=DamageType(source),
                fire_rate_boost=boost,
            )
        ]
    if m := _PER_STATUS_TYPE.fullmatch(line):
        return [
            Effect(
                stat=Stat.DIRECT_DAMAGE,
                value=_pct(m["value"]),
                per_status_type=True,
                trigger=ctx.trigger,
                trigger_damage_type=ctx.trigger_damage_type,
                duration_s=float(m["dur"]) if m["dur"] else None,
                max_stacks=int(m["stacks"]) if m["stacks"] else 1,
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


def _simple_list(line: str, ctx: Context) -> list[Effect] | None:
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
        stacks = stack_count(m, value) or stack_count(last, value)
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


def stack_count(m: re.Match[str], value: float) -> int | None:
    """ "12x" -> 12; a total cap "480%" with 12% per stack -> 40."""
    if m["stacks"]:
        return int(m["stacks"])
    if m["cap"] and value:
        return max(1, round(_pct(m["cap"]) / abs(value)))
    return None


def _pct(text: str) -> float:
    return round(float(text) / 100, 6)
