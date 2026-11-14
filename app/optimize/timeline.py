"""Damage events of one build over the fight (PLAN R1, steps 8b/8c).

Expected-value model: every shot of a build is the same, so procs per shot are expected
counts and debuff stacks are those counts over each debuff's window. Conditional effects come
resolved (`optimize.conditions`); the Galvanized-style bonus follows the status types on the
target shot by shot.
"""

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

from app.domain.class_mechanics import beam_level, sniper_combo_multiplier
from app.domain.combat import CAP_S, INDEX, TYPES, Event
from app.domain.debuffs import armor_kept
from app.domain.direct_bonus import DirectBonus
from app.domain.effects import DamageType, Faction
from app.domain.fire_rate import shot_times
from app.domain.headshot import Head
from app.domain.hit import with_direct_bonus
from app.domain.status import (
    blast_hits,
    blast_proc,
    dot_seed,
    dot_tick,
    dot_ticks,
    heat_ticks,
)
from app.domain.status_rules import StatusRules
from app.optimize.conditions import Resolved
from app.optimize.head import AOE, head_args
from app.optimize.loadout import Loadout
from app.optimize.procs import part_procs

HEAT = DamageType.HEAT
TIME_EPS = 1e-6  # s
POOLED = (HEAT,)  # Heat stacks share one tick and refresh each other (Heat_Damage:66)


@dataclass(frozen=True)
class Debuffs:
    armor_kept: float  # share of armor left after strips
    viral: float  # health damage factor
    magnetic: float  # shield damage factor


@dataclass
class Timeline:
    lo: Loadout
    res: Resolved
    head: Head | None
    bane: Faction | None
    rules: StatusRules
    until: float = CAP_S  # last shot time; a primer stops early (G49)
    shots: tuple[float, ...] | None = None  # shot times to use instead of the loadout's
    armored: dict[int, list[float]] = field(default_factory=dict)
    unarmored: dict[int, list[float]] = field(default_factory=dict)
    exact: dict[int, float] = field(default_factory=dict)  # merge key -> first event time

    def __post_init__(self) -> None:
        self.shot = self.res.shot
        if self.shot.hits:
            self.rules = self.rules.with_extra_stacks(self.shot.hits[0].stack_cap_bonus)
        self.window = {t: r.duration_s for t, r in self.rules.types.items()}  # base, s
        self.dots = {t: r.dot for t, r in self.rules.types.items() if r.dot is not None}
        self.times = (
            list(self.shots)
            if self.shots is not None
            else shot_times(self.shot.firing, self.shot.rate_factor, self.until)
        )
        self.own = [
            part_procs(hit, attack, self.lo.mark, self.head, self.shot, self.res.forced)
            for hit, (_, attack) in zip(self.shot.hits, self.lo.parts, strict=True)
        ]
        self.procs = self._procs_per_shot()
        self.duration = 1 + self.shot.hits[0].status_duration if self.shot.hits else 1.0
        stacking = self.rules.stacking
        self.debuff_rules = tuple(
            stacking(t) for t in (DamageType.CORROSIVE, DamageType.VIRAL, DamageType.MAGNETIC)
        )

    def events(self) -> list[Event]:
        if not self.times:  # never fires (fire-rate factor at or below 0): no damage
            return []
        hits, parts = self.shot.hits, self.lo.parts
        first = self.lo.parts[0][1]
        ramp = first.beam_ramp_start if first else self.lo.weapon.beam_ramp_start
        level, last = ramp or 1.0, 0.0  # beam damage share; time of the previous shot
        interval = 1 / self.shot.rate
        duration, procs = self.duration, self.procs
        rules = self.rules
        puncture, cold = rules.stacking(DamageType.PUNCTURE), rules.stacking(DamageType.COLD)
        heat: list[tuple[float, float, float, float]] = []  # time, seeds, procs, tick factor
        blast: list[tuple[float, float, float]] = []  # time, expected stacks, one stack
        combo_hits = 0.0
        for t in self.times:
            if ramp is not None:  # on target while firing; reloads are time off it
                off = max(0.0, t - last - interval)
                level = beam_level(ramp, level, t - last - off, off)
                last = t
            punct = self._stacks(procs, DamageType.PUNCTURE, t, duration)
            chill = self._stacks(procs, DamageType.COLD, t, duration)
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
                    chance_add=puncture.value(punct) if direct else 0.0,
                    damage_add=cold.value(chill) if direct else 0.0,
                ) * (self._combo(combo_hits) if direct else 1.0)
                if ramp is not None:
                    factor *= level  # one target from the first tick (V10)
                for dt, v in hit.damage.items():
                    self._add(t, dt, v * hit.multishot * factor)
                seed = dot_seed(hit.modded_base, factor)  # Bane already in `factor`
                bane = hit.faction_multiplier.get(self.bane, 1.0) if self.bane else 1.0
                for dt, p, ratio in own.seeded():
                    dot = self.dots.get(dt)
                    if dot is None:
                        continue
                    s = seed * ratio
                    bonus = hit.element_bonus.get(dt, 0.0)
                    status = hit.status_damage + hit.type_status_damage.get(dt, 0.0)
                    tick = dot_tick(dot, s, dt, bonus, bane, status)
                    if dt in POOLED:
                        heat.append((t, p * s, p, tick / (s + 1)))
                        continue
                    ticks = dot_ticks(dot, self.window[dt], hit.status_duration)
                    for j in range(ticks):
                        self._add(t + dot.first_tick_s + j, dt, p * tick, slash=True)
                if own.total.get(DamageType.BLAST):
                    stack = blast_proc(
                        rules.blast, hit.modded_base, factor, bane, hit.status_damage
                    )
                    blast.append((t, own.total[DamageType.BLAST], stack))
        self._heat(heat, duration)
        fuse = self.window[DamageType.BLAST] * duration
        for at, v in blast_hits(blast, fuse, rules.blast.cap):
            self._add(at, DamageType.BLAST, v)
        return self._with_debuffs()

    def _procs_per_shot(self) -> dict[DamageType, float]:
        out: dict[DamageType, float] = {}
        for own in self.own:
            for dt, p in own.total.items():
                out[dt] = out.get(dt, 0.0) + p
        return out

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
        duration: float,
    ) -> float:
        return self._live(procs, dt, t, self.window[dt] * duration)

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

    def status_types_at(self, t: float) -> float:
        return self._status_types(self.procs, t, self.duration)

    def _status_types(self, procs: dict[DamageType, float], t: float, duration: float) -> float:
        """Expected status types on the target for Galvanized-style bonuses: the bonus
        applies on the hits after the one that procs (Galvanized_Aptitude:42)."""
        return math.fsum(
            min(1.0, self._live(procs, dt, t, self.window[dt] * duration)) for dt in procs
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
        life = self.window[HEAT] * duration
        dot = self.dots[HEAT]
        per_shot = math.fsum(p for t, _, p, _ in heat if t == heat[0][0])
        gap = (self.times[1] - self.times[0]) / per_shot if len(self.times) > 1 else life
        procs = [(t, s, p) for t, s, p, _ in heat]
        for tick, v in heat_ticks(procs, heat[0][3], life, gap <= life, CAP_S, dot.first_tick_s):
            self._add(tick, HEAT, v)

    def _with_debuffs(self) -> list[Event]:
        zero = [0.0] * len(TYPES)
        out = []
        for key in sorted(self.armored.keys() | self.unarmored.keys()):
            t = self.exact[key]
            state = self.debuffs_at(t)
            out.append(
                Event(
                    time=t,
                    armored=self.armored.get(key, zero),
                    unarmored=self.unarmored.get(key, zero),
                    armor_kept=state.armor_kept,
                    viral=state.viral,
                    magnetic=state.magnetic,
                )
            )
        return out

    def debuffs_at(self, t: float) -> Debuffs:
        """The target's debuffs at `t` from the shots in `self.times`."""
        procs, duration = self.procs, self.duration
        corrosive, viral, magnetic = self.debuff_rules
        c = self._stacks(procs, DamageType.CORROSIVE, t, duration)
        v = self._stacks(procs, DamageType.VIRAL, t, duration)
        m = self._stacks(procs, DamageType.MAGNETIC, t, duration)
        return Debuffs(
            armor_kept(corrosive, c, self._heat_strip(t)),
            1 + viral.value(v),
            1 + magnetic.value(m),
        )

    def _heat_strip(self, t: float) -> float:
        """Heat's armor strip at `t`: ramps up from the shot where expected Heat procs reach
        one, holds while the shots keep it burning, returns after the last (Heat_Damage:81)."""
        p_heat, duration = self.procs.get(HEAT, 0.0), self.duration
        if not p_heat or not self.times:
            return 0.0
        first = math.ceil(1 / p_heat - 1e-9) - 1
        if first >= len(self.times) or t <= self.times[first]:
            return 0.0
        burning, strips = self.times[first], self.rules.heat_strip
        end = self.times[-1] + self.window[HEAT] * duration
        if t <= end:
            return strips.strip(t - burning, duration - 1)
        return strips.after_burn(strips.strip(end - burning, duration - 1), t - end)
