"""Conditional effects of a build resolved to bonuses (PLAN R2, G78).

Two passes: the first shot counts what needs no rate (unconditional, aiming, kill stacks at
max, headshot hit stacks at max on a head); its steady-state trigger rates (reloads
included) then set the stacks of the hit-, status-, reload- and first-shot-triggered
effects. Rates are not re-derived from the second pass (stated in /calc).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.conditions import (
    HEAD_HIT,
    HEAD_KILL,
    KILL,
    NEVER,
    first_shot_share,
    reload_uptime,
    steady_stacks,
    value_at,
)
from app.domain.crit import non_crit_chance
from app.domain.effects import DamageType, Effect, Operation, Stat, Trigger
from app.domain.fire_rate import reload_cycle, shooting_share, shots_per_magazine
from app.domain.hit import Bonus
from app.domain.stats import value_for
from app.gamedata.models import Effects
from app.optimize.evaluate import Loadout
from app.optimize.head import head_args
from app.optimize.shot import Shot, own_procs


@dataclass(frozen=True)
class Rates:
    """Triggers per second in steady state."""

    hits: float
    crits: float
    noncrits: float
    plain: float  # hits that neither crit nor proc a status
    procs: dict[DamageType, float]
    reload_cycle: float | None
    first_shot: float  # share of shots that open a magazine

    def of(self, e: Effect) -> float:
        if e.trigger == Trigger.ON_HIT:
            return self.hits
        if e.trigger == Trigger.ON_CRIT:
            return self.crits
        if e.trigger == Trigger.ON_NONCRIT_NO_STATUS:
            return self.plain
        if e.trigger == Trigger.ON_STATUS:
            if e.trigger_damage_type is None:
                return math.fsum(self.procs.values())
            return self.procs.get(e.trigger_damage_type, 0.0)
        return 0.0


@dataclass(frozen=True)
class Resolved:
    shot: Shot
    direct: float  # Galvanized-style bonus per status type on the target
    forced: tuple[Effect, ...]  # forced procs of mods (Hunter Munitions, Internal Bleeding)
    needs_kills: tuple[str, ...]  # entries counted at max kill stacks
    held: tuple[tuple[str, float, int], ...]  # entry, expected stacks, max stacks
    inactive: tuple[str, ...]  # entries with an effect whose condition a fight never meets


def resolve(lo: Loadout, on_head: bool) -> Resolved:
    """`on_head`: the shots land on a headshot spot (forms aimed at heads only)."""
    entries = lo.aimed() if lo.mark else lo.named
    first = _Pass(lo, on_head, None, entries)
    rates = _rates(lo, lo.shot(first.bonuses), on_head)
    full = _Pass(lo, on_head, rates, entries)
    return Resolved(
        shot=lo.shot(full.bonuses),
        direct=math.fsum(full.direct),
        forced=tuple(full.forced),
        needs_kills=tuple(full.needs_kills),
        held=tuple(full.held),
        inactive=tuple(full.inactive),
    )


class _Pass:
    def __init__(
        self,
        lo: Loadout,
        on_head: bool,
        rates: Rates | None,
        entries: Sequence[tuple[str, Effects]],
    ) -> None:
        self.lo, self.on_head, self.rates = lo, on_head, rates
        self.bonuses: list[Bonus] = []
        self.direct: list[float] = []
        self.forced: list[Effect] = []
        self.needs_kills: list[str] = []
        self.held: list[tuple[str, float, int]] = []
        self.inactive: list[str] = []
        for name, entry in entries:
            for e in entry.effects:
                self._add(name, e)

    def _add(self, name: str, e: Effect) -> None:
        if e.while_aiming and self.lo.mark is None:
            return
        if e.stat == Stat.FORCED_PROC and e.trigger != Trigger.ALWAYS:
            if self.rates is not None and e.trigger in (Trigger.ON_CRIT, Trigger.ON_STATUS):
                self.forced.append(e)
            return
        stacks = self._stacks(e)
        self._note(name, e, stacks)
        if stacks <= 0:
            return
        value = value_at(value_for(e, self.lo.weapon.weapon_type), e.operation, stacks)
        if e.stat == Stat.DIRECT_DAMAGE:
            self.direct.append(value)
        else:
            self.bonuses.append((e, value))

    def _stacks(self, e: Effect) -> float:
        t = e.trigger
        if t == Trigger.ALWAYS:
            return 1.0
        if t in NEVER:
            return 0.0
        if t in KILL:
            return float(e.max_stacks) if t not in HEAD_KILL or self.lo.mark else 0.0
        if t in HEAD_HIT:
            return float(e.max_stacks) if self.on_head else 0.0
        if self.rates is None:
            return 0.0
        if t == Trigger.FIRST_SHOT:
            return self.rates.first_shot
        if t == Trigger.ON_RELOAD:
            return reload_uptime(e.duration_s, self.rates.reload_cycle)
        if t == Trigger.ON_NONCRIT:
            # Only the non-crit branch itself is modelled: value = the expected factor there.
            instant = e.duration_s is None and e.stat == Stat.DAMAGE
            return e.chance if instant and e.operation == Operation.MULTIPLY else 0.0
        return steady_stacks(self.rates.of(e), e.duration_s, e.max_stacks, e.chance)

    def _note(self, name: str, e: Effect, stacks: float) -> None:
        t = e.trigger
        if t == Trigger.ALWAYS or self.rates is None:
            return
        if t in KILL and stacks > 0:
            _once(self.needs_kills, name)
        elif t in NEVER or (t in KILL | HEAD_HIT and self.lo.mark is None):
            _once(self.inactive, name)
        elif t not in KILL | HEAD_HIT | {Trigger.ON_NONCRIT} and all(
            n != name for n, _, _ in self.held
        ):
            self.held.append((name, stacks, e.max_stacks))


def _once(names: list[str], name: str) -> None:
    if name not in names:
        names.append(name)


def _rates(lo: Loadout, shot: Shot, on_head: bool) -> Rates:
    shots = shot.rate * shooting_share(shot.firing, shot.rate)
    hits, crits, noncrits, plain = [], [], [], []
    procs: dict[DamageType, float] = {}
    for hit, (_, attack) in zip(shot.hits, lo.parts, strict=True):
        args = head_args(attack, lo.mark) if lo.mark and on_head else None
        weak_point = args is not None and not args.flat
        miss = non_crit_chance(hit.head_critical_chance if weak_point else hit.critical_chance)
        n = shots * hit.multishot
        hits.append(n)
        crits.append(n * (1 - miss))
        noncrits.append(n * miss)
        if not (attack and attack.forced_procs):
            plain.append(n * miss * max(0.0, 1 - hit.status_chance))
        for dt, p in own_procs(hit, attack).items():
            procs[dt] = procs.get(dt, 0.0) + shots * p
    return Rates(
        hits=math.fsum(hits),
        crits=math.fsum(crits),
        noncrits=math.fsum(noncrits),
        plain=math.fsum(plain),
        procs=procs,
        reload_cycle=reload_cycle(shot.firing, shot.rate),
        first_shot=first_shot_share(shots_per_magazine(shot.firing)),
    )
