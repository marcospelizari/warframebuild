"""One fight against one enemy and its cost (PLAN R1, G32/G33/G37, C2/C3, G72).

Damage events come in time order with the target's debuff state at that moment. Shield is
hit first and takes no armor; Toxin goes straight to health; armor reduces health damage
only, `0.9·√(armor/2700)` (saved Armor:35); bleed (Slash DoT) is Cinematic damage: no armor
and no faction damage type modifier (Cinematic_Damage:9-13). Viral multiplies health
damage, Magnetic shield damage. TTK = time of the event that kills (no interpolation).
Not killed by the cap: cost `10 / f`, `f` = share of shield + health removed, floored.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.effects import DamageType

CAP_S = 10.0  # G33
MIN_REMOVED = 0.01  # C3
ARMOR_MAX_REDUCTION = 0.9
ARMOR_SCALE = 2700.0
TYPES = tuple(DamageType)
INDEX = {t: i for i, t in enumerate(TYPES)}


@dataclass(frozen=True)
class Event:
    time: float
    armored: Sequence[float]  # damage per type (TYPES order) that armor reduces
    unarmored: Sequence[float]  # Cinematic damage (bleed): no armor, no type modifier
    armor_kept: float  # share of armor left after strips
    viral: float  # health damage factor
    magnetic: float  # shield damage factor


@dataclass(frozen=True)
class Target:
    health: float
    shield: float
    armor: float
    modifiers: Sequence[float]  # faction damage type modifier per type (TYPES order)
    toxin_bypasses_shield: bool = True


@dataclass(frozen=True)
class Outcome:
    ttk: float | None  # None: alive at the cap
    removed: float  # share of shield + health removed by the kill or the cap
    cost: float


def armor_reduction(armor: float) -> float:
    if armor <= 0:
        return 0.0
    return min(ARMOR_MAX_REDUCTION, ARMOR_MAX_REDUCTION * math.sqrt(armor / ARMOR_SCALE))


def effective_hp(
    health: float,
    shield: float,
    armor: float,
    *,
    armor_kept: float = 1.0,
    viral: float = 1.0,
    magnetic: float = 1.0,
) -> float:
    """Damage a neutral hit (no damage type modifier, no Toxin) needs to remove shield and
    health: shield / Magnetic + health / (Viral x what armor lets through). Priming:37
    compares primers by this ratio (2700 armor stripped to 1998 = 4.428x less EHP)."""
    through = 1 - armor_reduction(armor * armor_kept)
    return shield / magnetic + health / (viral * through)


def fight(events: Sequence[Event], target: Target) -> Outcome:
    shield, health = target.shield, target.health
    bypass = INDEX[DamageType.TOXIN] if target.toxin_bypasses_shield else -1
    for e in events:
        if e.time > CAP_S:
            break
        kept = 1 - armor_reduction(target.armor * e.armor_kept)
        to_shield = through = rest = 0.0  # shield damage; health damage bypassing / behind it
        for k, m in enumerate(target.modifiers):
            a, u = e.armored[k], e.unarmored[k]
            if not a and not u:
                continue
            on_health = a * kept * m + u
            if k == bypass:
                through += on_health
            else:
                to_shield += a * m + u
                rest += on_health
        through *= e.viral
        rest *= e.viral
        to_shield *= e.magnetic
        if shield > 0 and to_shield > 0:
            if to_shield >= shield:
                rest *= (to_shield - shield) / to_shield  # the part past the shield
                shield = 0.0
            else:
                shield -= to_shield
                rest = 0.0
        health -= through + rest
        if health <= 0:
            return Outcome(e.time, 1.0, max(e.time, 1e-9))
    pool = target.health + target.shield
    removed = (target.shield - shield + target.health - health) / pool if pool else 1.0
    return Outcome(None, removed, CAP_S / max(removed, MIN_REMOVED))


def geometric_mean(costs: Sequence[float]) -> float:
    return math.exp(math.fsum(math.log(c) for c in costs) / len(costs))


def neutral_dps(events: Sequence[Event]) -> float:
    """Damage per second over the cap on a neutral target: health only, no armor, shields or
    faction modifiers; Viral still raises health damage (PLAN G80)."""
    total = math.fsum(
        (math.fsum(e.armored) + math.fsum(e.unarmored)) * e.viral for e in events if e.time <= CAP_S
    )
    return total / CAP_S
