"""Plain-Python evaluator: one candidate against every enemy (event loop, early exit)."""

import math
from collections.abc import Sequence

from app.domain.effects import DamageType
from bench.timeline import ARMOR_CAP, Event, events
from bench.workload import CAP_S, Enemy, ShotModel

MIN_REMOVED = 0.01  # C3: f floored at 0.01


def fight(
    types: tuple[DamageType, ...], timeline: Sequence[Event], enemy: Enemy, interval: float
) -> float:
    """C3 cost: kill time (+ one shot interval, R5 recommendation) or 10 / f."""
    fm = [enemy.faction[t] for t in types]
    bypass = [t == DamageType.TOXIN and enemy.toxin_bypass for t in types]
    k_range = range(len(types))
    shield, health, armor = enemy.shield, enemy.health, enemy.armor
    for t, arm, un, mag, vir, kept in timeline:
        af = 1 - min(ARMOR_CAP, 0.9 * math.sqrt(armor * kept / 2700))
        sp = hb = hnb = 0.0
        for k in k_range:
            a = arm[k]
            u = un[k]
            if a == 0 and u == 0:
                continue
            f = fm[k]
            if bypass[k]:
                hb += (a * af + u) * f
            else:
                sp += (a + u) * f
                hnb += (a * af + u) * f
        hb *= vir
        hnb *= vir
        sp *= mag
        if shield > 0:
            if sp >= shield:
                dmg = hb + (sp - shield) / sp * hnb
                shield = 0.0
            else:
                shield -= sp
                dmg = hb
        else:
            dmg = hb + hnb
        health -= dmg
        if health <= 0:
            return t + interval
    removed = (enemy.shield - shield + enemy.health - health) / (enemy.shield + enemy.health)
    return CAP_S / max(removed, MIN_REMOVED)


def costs(model: ShotModel, foes: Sequence[Enemy]) -> list[float]:
    types, timeline = events(model)
    return [fight(types, timeline, e, model.interval) for e in foes]


def score(model: ShotModel, foes: Sequence[Enemy]) -> float:
    """Geometric mean of the per-enemy cost (C12 search objective, equal weights)."""
    c = costs(model, foes)
    return math.exp(math.fsum(math.log(x) for x in c) / len(c))
