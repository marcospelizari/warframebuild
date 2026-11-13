"""Primer score (PLAN G49): how much more damage any follow-up hit does on primed enemies.

The primer fires a burst, then stops; over the follow-up window the boost is the enemy's
effective HP unprimed / primed (Viral, Magnetic and armor strips, Priming:37), averaged over
time. Enemies combine like the combat score: geometric mean per faction, then over the
factions. Body shots, no Bane: the follow-up weapon's own damage types are not known.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.combat import effective_hp, geometric_mean
from app.domain.status_rules import StatusRules
from app.gamedata.models import Enemy
from app.optimize.conditions import resolve
from app.optimize.loadout import Loadout
from app.optimize.timeline import Timeline

BURST_S = 2.0  # the primer fires this long (Marcos 2026-11-13)
FOLLOW_S = 6.0  # then the follow-up weapon hits for this long
SAMPLES = 60  # points in the follow-up window (midpoints of equal steps)


@dataclass(frozen=True)
class Primed:
    boost: float  # follow-up damage multiplier, combined over the enemies
    by_enemy: dict[str, float]  # uniqueName -> its time-averaged multiplier
    status_types: float  # different status types kept up, averaged over the window


def follow_up_times() -> list[float]:
    step = FOLLOW_S / SAMPLES
    return [BURST_S + (i + 0.5) * step for i in range(SAMPLES)]


def primed(lo: Loadout, enemies: Sequence[Enemy], rules: StatusRules) -> Primed:
    tl = Timeline(lo, resolve(lo, False), None, None, rules, until=BURST_S)
    times = follow_up_times()
    states = [tl.debuffs_at(t) for t in times]
    by_enemy: dict[str, float] = {}
    by_faction: dict[str, list[float]] = {}
    for e in enemies:
        plain = effective_hp(e.health, e.shield, e.armor)
        boosts = [
            plain
            / effective_hp(
                e.health,
                e.shield,
                e.armor,
                armor_kept=s.armor_kept,
                viral=s.viral,
                magnetic=s.magnetic,
            )
            for s in states
        ]
        by_enemy[e.unique_name] = math.fsum(boosts) / len(boosts)
        by_faction.setdefault(e.faction, []).append(by_enemy[e.unique_name])
    factions = [geometric_mean(v) for _, v in sorted(by_faction.items())]
    return Primed(
        boost=geometric_mean(factions) if factions else 1.0,
        by_enemy=by_enemy,
        status_types=math.fsum(tl.status_types_at(t) for t in times) / len(times),
    )
