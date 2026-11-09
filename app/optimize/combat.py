"""Combat score of one build against the representative enemies (PLAN R1, step 8b).

Expected-value model: every shot of a build is the same, so procs per shot are expected
counts and debuff stacks are those counts over each debuff's window. One timeline per
(head, Bane faction) is shared by the enemies that have them; `domain.combat.fight` then
plays it against each enemy. A form aimed at heads hits each enemy's own head spot (the body
if it has none) with its head bonuses at max hit stacks, as /calc ranks head DPS (G70).
"""

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

from app.domain import debuffs
from app.domain.class_mechanics import beam_ramp, sniper_combo_multiplier
from app.domain.combat import CAP_S, INDEX, TYPES, Event, Outcome, Target, fight, geometric_mean
from app.domain.effects import DamageType, Faction
from app.domain.fire_rate import shot_times
from app.domain.headshot import Head
from app.domain.hit import ModdedHit
from app.domain.status import (
    BASE_DURATION_S,
    BLAST_STACK_S,
    FIRST_TICK_S,
    blast_hits,
    blast_proc,
    dot_seed,
    dot_tick,
    dot_ticks,
    expected_procs,
    heat_ticks,
    proc_shares,
)
from app.gamedata.models import Attack, Enemy, FactionModifiers
from app.optimize.evaluate import Loadout
from app.optimize.head import AOE, head_args
from app.optimize.shot import Shot

HEAT = DamageType.HEAT
TIME_EPS = 1e-6  # s
POOLED = (HEAT,)  # Heat stacks share one tick and refresh each other (Heat_Damage:66)


@dataclass(frozen=True)
class EnemyResult:
    enemy: Enemy
    outcome: Outcome


@dataclass(frozen=True)
class Combat:
    enemies: list[EnemyResult]
    factions: dict[str, float]  # geometric mean cost per faction
    score: float  # geometric mean over the factions


def timeline(lo: Loadout, enemy: Enemy) -> list[Event]:
    """Damage events of `lo` against `enemy` (before its faction modifiers and defences)."""
    head, bane = _key(lo, enemy)
    return _Timeline(lo, _shot(lo, head), head, bane).events()


def _shot(lo: Loadout, head: Head | None) -> Shot:
    """Aimed forms aim (zoom, aiming bonuses); headshot-triggered bonuses (at max stacks,
    G70) only on an enemy that has a headshot spot."""
    if lo.mark is None:
        return lo.shot(lo.body_bonuses())
    return lo.shot(lo.head_bonuses(head is not None))


def _key(lo: Loadout, enemy: Enemy) -> tuple[Head | None, Faction | None]:
    head = enemy.head if lo.mark is not None else None
    return (Head(head.multiplier, head.critical) if head else None, enemy.bane)


def combat(lo: Loadout, enemies: list[Enemy], factions: list[FactionModifiers]) -> Combat:
    modifiers = {f.faction: f.modifiers for f in factions}
    shots: dict[bool, Shot] = {}
    timelines: dict[tuple[Head | None, Faction | None], list[Event]] = {}
    results = []
    for e in enemies:
        key = _key(lo, e)
        if key not in timelines:
            aimed_at_head = key[0] is not None
            if aimed_at_head not in shots:
                shots[aimed_at_head] = _shot(lo, key[0])
            timelines[key] = _Timeline(lo, shots[aimed_at_head], *key).events()
        mods = modifiers[e.faction]
        target = Target(
            health=e.health,
            shield=e.shield,
            armor=e.armor,
            modifiers=tuple(mods.get(t, 1.0) for t in TYPES),
            toxin_bypasses_shield=e.toxin_bypasses_shield,
        )
        results.append(EnemyResult(e, fight(timelines[key], target)))
    by_faction: dict[str, list[float]] = {}
    for r in results:
        by_faction.setdefault(r.enemy.faction, []).append(r.outcome.cost)
    scores = {f: geometric_mean(c) for f, c in sorted(by_faction.items())}
    return Combat(results, scores, geometric_mean(list(scores.values())) if scores else 0.0)


@dataclass
class _Timeline:
    lo: Loadout
    shot: Shot
    head: Head | None
    bane: Faction | None
    armored: dict[int, list[float]] = field(default_factory=dict)
    unarmored: dict[int, list[float]] = field(default_factory=dict)
    exact: dict[int, float] = field(default_factory=dict)  # merge key -> first event time

    def __post_init__(self) -> None:
        self.times = shot_times(self.shot.firing, self.shot.rate_factor, CAP_S)

    def events(self) -> list[Event]:
        hits, parts = self.shot.hits, self.lo.parts
        ramp = self.lo.weapon.beam_ramp_start
        duration = 1 + hits[0].status_duration
        procs = self._procs_per_shot()
        heat: list[tuple[float, float, float, float]] = []  # time, seeds, procs, tick factor
        blast: list[tuple[float, float, float]] = []  # time, expected stacks, one stack
        combo_hits = 0.0
        for t in self.times:
            punct = self._stacks(procs, DamageType.PUNCTURE, t, debuffs.PUNCTURE, duration)
            cold = self._stacks(procs, DamageType.COLD, t, debuffs.COLD, duration)
            for hit, (_, attack) in zip(hits, parts, strict=True):
                args = head_args(attack, self.lo.mark) if self.lo.mark else None
                direct = attack is None or attack.shot_type != AOE
                if direct:
                    combo_hits += hit.multishot
                on_head = self.head if args is not None else None
                factor = hit.hit_factor(
                    self.bane,
                    on_head,
                    flat=bool(args and args.flat),
                    extra_bonus=args.extra_bonus if args else 0.0,
                    extra_factor=args.extra_factor if args else 0.0,
                    chance_add=debuffs.PUNCTURE.value(punct) if direct else 0.0,
                    damage_add=debuffs.COLD.value(cold) if direct else 0.0,
                ) * (self._combo(combo_hits) if direct else 1.0)
                if ramp is not None:
                    factor *= beam_ramp(ramp, t)  # one target from the first tick (V10)
                for dt, v in hit.damage.items():
                    self._add(t, dt, v * hit.multishot * factor)
                seed = dot_seed(hit.modded_base, factor)  # Bane already in `factor`
                bane = hit.faction_multiplier.get(self.bane, 1.0) if self.bane else 1.0
                own = self._own_procs(hit, attack)
                for dt in FIRST_TICK_S:
                    p = own.get(dt, 0.0)
                    if not p:
                        continue
                    tick = dot_tick(
                        seed, dt, hit.element_bonus.get(dt, 0.0), bane, hit.status_damage
                    )
                    if dt in POOLED:
                        heat.append((t, p * seed, p, tick / (seed + 1)))
                        continue
                    for j in range(dot_ticks(dt, hit.status_duration)):
                        self._add(t + FIRST_TICK_S[dt] + j, dt, p * tick, slash=True)
                if own.get(DamageType.BLAST):
                    stack = blast_proc(hit.modded_base, factor, bane, hit.status_damage)
                    blast.append((t, own[DamageType.BLAST], stack))
        self._heat(heat, duration)
        for at, v in blast_hits(blast, BLAST_STACK_S * duration):
            self._add(at, DamageType.BLAST, v)
        return self._with_debuffs(procs, duration)

    def _procs_per_shot(self) -> dict[DamageType, float]:
        out: dict[DamageType, float] = {}
        for hit, (_, attack) in zip(self.shot.hits, self.lo.parts, strict=True):
            for dt, p in self._own_procs(hit, attack).items():
                out[dt] = out.get(dt, 0.0) + p
        return out

    @staticmethod
    def _own_procs(hit: ModdedHit, attack: Attack | None) -> dict[DamageType, float]:
        forced = (attack.forced_procs or []) if attack is not None else []
        each = expected_procs(hit.status_chance, proc_shares(hit.damage), forced)
        return {t: p * hit.multishot for t, p in each.items() if isinstance(t, DamageType)}

    def _combo(self, hits: float) -> float:
        minimum = self.lo.weapon.sniper_combo_min
        if not minimum or self.lo.mark is None:
            return 1.0  # sniper combo builds only while scoped (Sniper_Rifle)
        return sniper_combo_multiplier(math.floor(hits + 1e-9), minimum)

    def _stacks(
        self,
        procs: dict[DamageType, float],
        dt: DamageType,
        t: float,
        stacking: debuffs.Stacking,
        duration: float,
    ) -> float:
        """Expected stacks at `t` from earlier shots inside the stack duration."""
        p = procs.get(dt, 0.0)
        if not p:
            return 0.0
        before = t - TIME_EPS  # a shot's own procs never count at its own time
        shots = bisect_left(self.times, before) - bisect_right(
            self.times, before - stacking.duration_s * duration
        )
        return p * shots

    def _add(self, t: float, dt: DamageType, v: float, *, slash: bool = False) -> None:
        if t > CAP_S or not v:
            return
        unarmored = slash and dt == DamageType.SLASH  # bleed: Cinematic damage
        table = self.unarmored if unarmored else self.armored
        key = round(t / TIME_EPS)  # events this close are one (float drift in sums)
        self.exact.setdefault(key, t)
        row = table.setdefault(key, [0.0] * len(TYPES))
        row[INDEX[dt]] += v

    def _heat(self, heat: list[tuple[float, float, float, float]], duration: float) -> None:
        """Expected Heat procs closer together than the burn keep it going (each refreshes
        all stacks); sparser ones each last one duration."""
        if not heat:
            return
        life = BASE_DURATION_S * duration
        per_shot = math.fsum(p for t, _, p, _ in heat if t == heat[0][0])
        gap = (self.times[1] - self.times[0]) / per_shot if len(self.times) > 1 else life
        procs = [(t, s, p) for t, s, p, _ in heat]
        for tick, v in heat_ticks(procs, heat[0][3], life, gap <= life, CAP_S):
            self._add(tick, HEAT, v)

    def _with_debuffs(self, procs: dict[DamageType, float], duration: float) -> list[Event]:
        p_heat = procs.get(HEAT, 0.0)
        burning = None
        if p_heat:
            first = math.ceil(1 / p_heat - 1e-9) - 1  # shot where expected Heat procs reach 1
            burning = self.times[first] if first < len(self.times) else None
        zero = [0.0] * len(TYPES)
        out = []
        for key in sorted(self.armored.keys() | self.unarmored.keys()):
            t = self.exact[key]
            strip = (
                debuffs.heat_strip(t - burning, duration - 1)
                if burning is not None and t > burning
                else 0.0
            )
            c = self._stacks(procs, DamageType.CORROSIVE, t, debuffs.CORROSIVE, duration)
            v = self._stacks(procs, DamageType.VIRAL, t, debuffs.VIRAL, duration)
            m = self._stacks(procs, DamageType.MAGNETIC, t, debuffs.MAGNETIC, duration)
            out.append(
                Event(
                    time=t,
                    armored=self.armored.get(key, zero),
                    unarmored=self.unarmored.get(key, zero),
                    armor_kept=debuffs.armor_kept(c, strip),
                    viral=1 + debuffs.VIRAL.value(v),
                    magnetic=1 + debuffs.MAGNETIC.value(m),
                )
            )
        return out
