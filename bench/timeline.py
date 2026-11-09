"""Enemy-independent part of one fight: when shots, DoT ticks and Blast events land, and
the debuff state (Corrosive / Heat strip, Viral, Magnetic) at each event.

In the expected-value model every shot of a candidate is identical, so each shot spawns
the same events at fixed offsets (0 = the hit, then one per DoT second). Strip and amp
curves are stand-ins with the step-8 cost shape (stack counts over a sliding window,
Heat steps from its first proc), not decided rules.
"""

import math
from bisect import bisect_left
from collections import deque
from dataclasses import dataclass

from app.domain.effects import DamageType
from app.domain.status import BLAST_CAP, BLAST_STACK_S, FIRST_TICK_S, blast_detonation
from bench.workload import CAP_S, ShotModel

HEAT_STEPS = ((0.5, 0.85), (1.0, 0.70), (1.5, 0.60))  # (elapsed below, armor kept); then 0.50
ARMOR_CAP = 0.9


@dataclass(frozen=True)
class Offsets:
    types: tuple[DamageType, ...]
    armored: list[list[float]]  # per offset: damage per type that armor reduces
    unarmored: list[list[float]]  # per offset: Slash DoT (ignores armor)


def damage_types(model: ShotModel) -> tuple[DamageType, ...]:
    found = set(model.direct) | set(model.dot_tick)
    if model.procs.get(DamageType.BLAST):
        found.add(DamageType.BLAST)
    return tuple(sorted(found))


def offsets(model: ShotModel) -> Offsets:
    types = damage_types(model)
    index = {t: i for i, t in enumerate(types)}
    last = max([0] + [int(FIRST_TICK_S[t]) + n - 1 for t, n in model.dot_ticks.items() if n > 0])
    armored = [[0.0] * len(types) for _ in range(last + 1)]
    unarmored = [[0.0] * len(types) for _ in range(last + 1)]
    for t, v in model.direct.items():
        armored[0][index[t]] += v
    for t, tick in model.dot_tick.items():
        first = int(FIRST_TICK_S[t])
        target = unarmored if t == DamageType.SLASH else armored
        for j in range(model.dot_ticks[t]):
            target[first + j][index[t]] += model.procs[t] * tick
    return Offsets(types, armored, unarmored)


def shot_times(model: ShotModel) -> list[float]:
    out: list[float] = []
    t = 0.0
    while t <= CAP_S:
        out.append(t)
        if model.shots_per_mag and len(out) % model.shots_per_mag == 0:
            t += model.reload
        else:
            t += model.interval
    return out


def blast_events(model: ShotModel, shots: list[float]) -> list[tuple[float, float]]:
    """(time, Blast damage) of detonations and expiries; expected stacks per shot."""
    per_shot = model.procs.get(DamageType.BLAST, 0.0)
    if not per_shot:
        return []
    hit = math.fsum(model.direct.values())
    stacks: deque[tuple[float, float]] = deque()  # (applied at, expected stacks)
    out: list[tuple[float, float]] = []
    for t in shots:
        while stacks and stacks[0][0] + BLAST_STACK_S <= t:
            applied, n = stacks.popleft()
            out.append((applied + BLAST_STACK_S, n * max(1.0, 0.3 * hit)))
        stacks.append((t, per_shot))
        total = math.fsum(n for _, n in stacks)
        if total >= BLAST_CAP:
            out.append((t, blast_detonation([hit * total])))
            stacks.clear()
    out += [(a + BLAST_STACK_S, n * max(1.0, 0.3 * hit)) for a, n in stacks]
    return [(t, v) for t, v in out if t <= CAP_S]


def heat_start(model: ShotModel, shots: list[float]) -> float | None:
    """Time of the shot where the expected Heat procs reach 1 (strip starts after it)."""
    p = model.procs.get(DamageType.HEAT, 0.0)
    if p <= 0:
        return None
    index = math.ceil(1 / p - 1e-12) - 1
    return shots[index] if index < len(shots) else None


def corrosive_kept(n: float) -> float:
    if n <= 0:
        return 1.0
    if n < 1:
        return 1 - 0.26 * n
    return 1 - min(0.8, 0.26 + 0.06 * (n - 1))


def heat_kept(elapsed: float) -> float:
    if elapsed <= 0:
        return 1.0
    for below, kept in HEAT_STEPS:
        if elapsed < below:
            return kept
    return 0.5


def amp(n: float) -> float:
    """Viral (health) and Magnetic (shield) amplification by expected stacks."""
    if n <= 0:
        return 1.0
    if n < 1:
        return 1 + n
    return 2 + 0.25 * (min(n, 10.0) - 1)


Event = tuple[float, list[float], list[float], float, float, float]  # t, arm, un, mag, vir, kept


def events(model: ShotModel) -> tuple[tuple[DamageType, ...], list[Event]]:
    """Plain-Python timeline: every event in time order with its debuff state."""
    o = offsets(model)
    shots = shot_times(model)
    raw: list[tuple[float, list[float], list[float]]] = []
    for s in shots:
        for k in range(len(o.armored)):
            if s + k <= CAP_S:
                raw.append((s + k, o.armored[k], o.unarmored[k]))
    if DamageType.BLAST in o.types:
        b = o.types.index(DamageType.BLAST)
        zero = [0.0] * len(o.types)
        for t, v in blast_events(model, shots):
            vec = list(zero)
            vec[b] = v
            raw.append((t, vec, zero))
    raw.sort(key=lambda e: e[0])
    heat = heat_start(model, shots)
    pc = model.procs.get(DamageType.CORROSIVE, 0.0)
    pv = model.procs.get(DamageType.VIRAL, 0.0)
    pm = model.procs.get(DamageType.MAGNETIC, 0.0)
    out: list[Event] = []
    for t, arm, un in raw:
        active = bisect_left(shots, t) - bisect_left(shots, t - model.duration)
        kept = corrosive_kept(pc * active) * (heat_kept(t - heat) if heat is not None else 1.0)
        out.append((t, arm, un, amp(pm * active), amp(pv * active), kept))
    return o.types, out
