"""Damage events of one build over the fight (PLAN R1, steps 8b/8c).

Expected-value model: every shot of a build is the same, so procs per shot are expected
counts and debuff stacks are those counts over each debuff's window. Conditional effects come
resolved (`optimize.conditions`); the Galvanized-style bonus follows the status types on the
target shot by shot.
"""

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

from app.domain import debuffs
from app.domain.class_mechanics import beam_level, sniper_combo_multiplier
from app.domain.combat import CAP_S, INDEX, TYPES, Event
from app.domain.crit import non_crit_chance
from app.domain.direct_bonus import DirectBonus
from app.domain.effects import DamageType, Faction, Trigger
from app.domain.fire_rate import shot_times
from app.domain.headshot import Head
from app.domain.hit import ModdedHit, with_direct_bonus
from app.domain.status import (
    BASE_DURATION_S,
    BLAST_STACK_S,
    FIRST_TICK_S,
    STATUS_S,
    blast_hits,
    blast_proc,
    boosted,
    chance_of_at_least_one,
    combined_chance,
    dot_seed,
    dot_tick,
    dot_ticks,
    heat_ticks,
    proc_shares,
)
from app.gamedata.models import Attack
from app.optimize.conditions import Resolved
from app.optimize.evaluate import Loadout
from app.optimize.head import AOE, head_args
from app.optimize.shot import own_procs

HEAT = DamageType.HEAT
TIME_EPS = 1e-6  # s
POOLED = (HEAT,)  # Heat stacks share one tick and refresh each other (Heat_Damage:66)


@dataclass(frozen=True)
class _Procs:
    """Expected procs of one shot part per shot."""

    normal: dict[DamageType, float]  # seeded by the average hit
    on_crit: dict[DamageType, float]  # applied by crits only: seeded by the average crit
    crit_ratio: float  # average crit multiplier / average hit multiplier

    @property
    def total(self) -> dict[DamageType, float]:
        keys = sorted(self.normal.keys() | self.on_crit.keys())
        return {t: self.normal.get(t, 0.0) + self.on_crit.get(t, 0.0) for t in keys}

    def seeded(self) -> list[tuple[DamageType, float, float]]:
        """(type, procs, seed ratio) with procs > 0."""
        out = [(t, p, 1.0) for t, p in self.normal.items() if p]
        return out + [(t, p, self.crit_ratio) for t, p in self.on_crit.items() if p]


@dataclass
class Timeline:
    lo: Loadout
    res: Resolved
    head: Head | None
    bane: Faction | None
    armored: dict[int, list[float]] = field(default_factory=dict)
    unarmored: dict[int, list[float]] = field(default_factory=dict)
    exact: dict[int, float] = field(default_factory=dict)  # merge key -> first event time

    def __post_init__(self) -> None:
        self.shot = self.res.shot
        self.times = shot_times(self.shot.firing, self.shot.rate_factor, CAP_S)
        self.own = [
            self._part_procs(hit, attack)
            for hit, (_, attack) in zip(self.shot.hits, self.lo.parts, strict=True)
        ]

    def events(self) -> list[Event]:
        hits, parts = self.shot.hits, self.lo.parts
        first = self.lo.parts[0][1]
        ramp = first.beam_ramp_start if first else self.lo.weapon.beam_ramp_start
        level, last = ramp or 1.0, 0.0  # beam damage share; time of the previous shot
        interval = 1 / self.shot.rate
        duration = 1 + hits[0].status_duration
        procs = self._procs_per_shot()
        heat: list[tuple[float, float, float, float]] = []  # time, seeds, procs, tick factor
        blast: list[tuple[float, float, float]] = []  # time, expected stacks, one stack
        combo_hits = 0.0
        for t in self.times:
            if ramp is not None:  # on target while firing; reloads are time off it
                off = max(0.0, t - last - interval)
                level = beam_level(ramp, level, t - last - off, off)
                last = t
            punct = self._stacks(procs, DamageType.PUNCTURE, t, debuffs.PUNCTURE, duration)
            cold = self._stacks(procs, DamageType.COLD, t, debuffs.COLD, duration)
            types = self._status_types(procs, t, duration) if self.res.direct else 0.0
            for base, (_, attack), own in zip(hits, parts, self.own, strict=True):
                args = head_args(attack, self.lo.mark) if self.lo.mark else None
                direct = attack is None or attack.shot_type != AOE
                behaviour = attack.direct_bonus if attack else DirectBonus.ADDING
                hit = with_direct_bonus(base, behaviour, self.res.direct * types) if types else base
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
                    factor *= level  # one target from the first tick (V10)
                for dt, v in hit.damage.items():
                    self._add(t, dt, v * hit.multishot * factor)
                seed = dot_seed(hit.modded_base, factor)  # Bane already in `factor`
                bane = hit.faction_multiplier.get(self.bane, 1.0) if self.bane else 1.0
                for dt, p, ratio in own.seeded():
                    if dt not in FIRST_TICK_S:
                        continue
                    s = seed * ratio
                    tick = dot_tick(s, dt, hit.element_bonus.get(dt, 0.0), bane, hit.status_damage)
                    if dt in POOLED:
                        heat.append((t, p * s, p, tick / (s + 1)))
                        continue
                    for j in range(dot_ticks(dt, hit.status_duration)):
                        self._add(t + FIRST_TICK_S[dt] + j, dt, p * tick, slash=True)
                if own.total.get(DamageType.BLAST):
                    stack = blast_proc(hit.modded_base, factor, bane, hit.status_damage)
                    blast.append((t, own.total[DamageType.BLAST], stack))
        self._heat(heat, duration)
        for at, v in blast_hits(blast, BLAST_STACK_S * duration):
            self._add(at, DamageType.BLAST, v)
        return self._with_debuffs(procs, duration)

    def _procs_per_shot(self) -> dict[DamageType, float]:
        out: dict[DamageType, float] = {}
        for own in self.own:
            for dt, p in own.total.items():
                out[dt] = out.get(dt, 0.0) + p
        return out

    def _part_procs(self, hit: ModdedHit, attack: Attack | None) -> "_Procs":
        """Procs of one shot part: its own, plus the forced procs of mods (Hunter Munitions on
        crits, Internal Bleeding on Impact procs): sources of one type apply it at most once
        per projectile (checklist, Hunter Munitions + Internal Bleeding)."""
        normal = own_procs(hit, attack)
        args = head_args(attack, self.lo.mark) if self.lo.mark else None
        head = self.head if args is not None else None
        flat = bool(args and args.flat)
        f = self.shot.firing
        rate = f.fire_rate * self.shot.rate_factor if f.fire_rate else self.shot.rate
        shares = proc_shares(hit.damage)
        guaranteed = set((attack.forced_procs or []) if attack else [])
        crit: dict[DamageType, list[float]] = {}
        other: dict[DamageType, list[float]] = {}
        for e in self.res.forced:
            if e.damage_type is None:
                continue
            value = boosted(e.value, e.fire_rate_boost, rate)
            if e.trigger == Trigger.ON_CRIT:
                p = value * (1 - non_crit_chance(hit.crit_chance(head, flat=flat)))
                crit.setdefault(e.damage_type, []).append(p)
                continue
            on = e.trigger_damage_type
            if on in guaranteed:
                met = 1.0
            else:
                share = shares.get(on, 0.0) if on else 1.0
                met = chance_of_at_least_one(hit.status_chance, share)
            other.setdefault(e.damage_type, []).append(value * met)
        on_crit: dict[DamageType, float] = {}
        for dt in sorted(crit.keys() | other.keys()):
            first = combined_chance(crit.get(dt, []))
            both = combined_chance(crit.get(dt, []) + other.get(dt, []))
            on_crit[dt] = first * hit.multishot
            normal[dt] = normal.get(dt, 0.0) + (both - first) * hit.multishot
        return _Procs(normal, on_crit, hit.crit_only_ratio(head, flat=flat))

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
        return self._live(procs, dt, t, stacking.duration_s * duration)

    def _live(
        self, procs: dict[DamageType, float], dt: DamageType, t: float, window: float
    ) -> float:
        """Expected procs on the target at `t` from earlier shots inside `window` seconds."""
        p = procs.get(dt, 0.0)
        if not p:
            return 0.0
        before = t - TIME_EPS  # a shot's own procs never count at its own time
        shots = bisect_left(self.times, before) - bisect_right(self.times, before - window)
        return p * shots

    def _status_types(self, procs: dict[DamageType, float], t: float, duration: float) -> float:
        """Expected status types on the target for Galvanized-style bonuses: the bonus
        applies on the hits after the one that procs (Galvanized_Aptitude:42)."""
        return math.fsum(
            min(1.0, self._live(procs, dt, t, STATUS_S[dt] * duration)) for dt in procs
        )

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
