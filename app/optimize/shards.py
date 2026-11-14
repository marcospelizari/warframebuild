"""Archon Shards beside a build (G91): the build is fixed, shards are added slot by slot."""

from dataclasses import replace

from app.domain.archon_shards import SLOTS, ArchonShards, Shard
from app.domain.effects import DamageType, Support
from app.domain.status_rules import StatusRules
from app.gamedata.builds import ShardAdvice, ShardStep
from app.gamedata.models import Effects
from app.optimize.conditions import resolve
from app.optimize.loadout import Loadout
from app.optimize.scoring import Objective
from app.optimize.search import rounded
from app.optimize.timeline import Timeline

NAME = "Archon Shards"


def with_shards(
    lo: Loadout,
    table: ArchonShards,
    chosen: list[Shard],
    tauforged: bool,
    applied: frozenset[DamageType] = frozenset(),
) -> Loadout:
    """`lo` with the shards' gun buffs after the mods (their elements combine last)."""
    effects = table.effects(chosen, lo.weapon.category.value, tauforged, applied)
    if not effects:
        return lo
    entry = Effects(support=Support.FULL, effects=effects, unparsed=[])
    return replace(lo, named=[*lo.named, (NAME, entry)])


def advice(
    lo: Loadout, table: ArchonShards, rules: StatusRules, objective: Objective
) -> ShardAdvice:
    applied = applied_statuses(lo, rules)
    normal = _steps(lo, table, objective, False, applied)
    chosen = [s.shard for s in normal]
    return ShardAdvice(
        normal=normal,
        tauforged=_steps(lo, table, objective, True, applied),
        conditions=table.conditions(chosen, lo.weapon.category.value, applied),
    )


def applied_statuses(lo: Loadout, rules: StatusRules) -> frozenset[DamageType]:
    """Statuses the build itself puts on enemies (any expected procs per shot)."""
    procs = Timeline(lo, resolve(lo, False), None, None, rules).procs
    return frozenset(t for t, p in procs.items() if p > 0)


def _steps(
    lo: Loadout,
    table: ArchonShards,
    objective: Objective,
    tauforged: bool,
    applied: frozenset[DamageType],
) -> list[ShardStep]:
    candidates = table.candidates(lo.weapon.category.value, applied)
    chosen: list[Shard] = []
    best = objective(lo)
    steps = []
    while len(chosen) < SLOTS and candidates:
        scored = [
            (objective(with_shards(lo, table, [*chosen, s], tauforged, applied)), s)
            for s in candidates
        ]
        score, shard = max(scored, key=lambda x: x[0])  # first of equals: colour order
        if score <= best:
            break  # no shard gains: the slot is better spent on the frame
        chosen.append(shard)
        best = score
        steps.append(ShardStep(shard=shard, score=rounded(score)))
    return steps
