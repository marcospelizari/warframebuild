"""Step 4.5 spike workload (#19, PLAN C9): real guns and mods, synthetic enemies.

Guns, mods and the per-candidate hit come from committed `gamedata/` through the real
domain code (`modded_hit`, `effective_fire_rate`, `modded`). Everything that step 8 has
not decided yet is a stand-in with the right *cost shape*, never a game fact:

- enemies: seeded random health / shield / armor / faction multipliers, scaled to the
  gun so fights range from a fraction of a second to past the 10 s cap;
- mod pool: category + compat name match, no compatibility tags (step 8);
- conditional effects: all at max stacks.

Nothing here is read by `app/`; the numbers it produces are timings, not builds.
"""

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.domain import crit
from app.domain.effects import DamageType, Stat, Trigger
from app.domain.fire_rate import Firing, effective_fire_rate
from app.domain.hit import AttackStats, Bonus, modded_hit
from app.domain.stats import modded, modded_time, value_for
from app.domain.status import (
    BASE_DURATION_S,
    FIRST_TICK_S,
    dot_seed,
    dot_tick,
    dot_ticks,
    expected_procs,
    proc_shares,
)
from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData, load

ROOT = Path(__file__).resolve().parents[1]
WEAPONS = (
    "Baza Prime",  # fastest auto, Slash DoT
    "Soma Prime",  # auto, 200 magazine
    "Ignis Wraith",  # held, Heat
    "Hek",  # shotgun, multishot 7
    "Rubico Prime",  # sniper
    "Kuva Bramma",  # charge launcher, Blast
    "Lex Prime",  # semi pistol
)
ENEMIES = 16  # ~2 per main faction (R1/E2)
CAP_S = 10.0  # simulation cap (G33)
DOT_TYPES = tuple(FIRST_TICK_S)
USED_TRIGGERS = frozenset({Trigger.ALWAYS, Trigger.ON_HIT, Trigger.ON_KILL, Trigger.ON_CRIT})
POOL_COMPAT = {
    "Rifle": ("Rifle", "Assault Rifle", "PRIMARY"),
    "Sniper": ("Rifle", "Sniper", "PRIMARY"),
    "Bow": ("Rifle", "Bow", "PRIMARY"),
    "Launcher": ("Rifle", "PRIMARY"),
    "Shotgun": ("Shotgun", "PRIMARY"),
}


@dataclass(frozen=True)
class ShotModel:
    """One candidate as the combat evaluator sees it: enemy-independent expected values."""

    interval: float  # s between shots
    shots_per_mag: int | None  # None = never reloads
    reload: float  # s
    direct: dict[DamageType, float]  # expected direct damage per shot (crit avg, multishot)
    procs: dict[DamageType, float]  # expected procs per shot per damage type
    dot_tick: dict[DamageType, float]  # damage of one tick of one proc
    dot_ticks: dict[DamageType, int]
    duration: float  # status duration, s
    burst_dps: float  # the Max metric (Q2)


@dataclass(frozen=True)
class Enemy:
    health: float
    shield: float
    armor: float
    faction: dict[DamageType, float]  # damage-type multiplier
    toxin_bypass: bool


def gamedata() -> GameData:
    return load(ROOT / "gamedata")


def pool(data: GameData, weapon: Weapon) -> list[Mod]:
    compat = POOL_COMPAT.get(weapon.weapon_type, ("Pistol", "SECONDARY"))
    return [
        m
        for m in data.mods.mods
        if m.category == weapon.category
        and (m.compat_name in compat or m.compat_name == weapon.name)
        and m.effects.effects
        and not m.exilus
    ]


def candidates(mods: Sequence[Mod], count: int, seed: int) -> list[list[Mod]]:
    """`count` random 8-mod sets without family clashes (deterministic per seed)."""
    rng = random.Random(seed)
    out: list[list[Mod]] = []
    while len(out) < count:
        picked: list[Mod] = []
        families: set[str] = set()
        for m in rng.sample(list(mods), len(mods)):
            if m.family and m.family in families:
                continue
            picked.append(m)
            if m.family:
                families.add(m.family)
            if len(picked) == 8:
                break
        out.append(picked)
    return out


def bonuses(weapon: Weapon, mods: Sequence[Mod]) -> list[Bonus]:
    out: list[Bonus] = []
    for m in mods:
        for e in m.effects.effects:
            if e.trigger in USED_TRIGGERS and e.stat not in (Stat.DIRECT_DAMAGE, Stat.FORCED_PROC):
                out.append((e, value_for(e, weapon.weapon_type, e.max_stacks)))
    return out


def shot_model(weapon: Weapon, mods: Sequence[Mod]) -> ShotModel:
    """Per-candidate work done before any enemy: the real domain hit and fire rate."""
    b = bonuses(weapon, mods)
    attack = weapon.attacks[0]
    hit = modded_hit(
        AttackStats(
            damage=weapon.damage,
            critical_chance=weapon.critical_chance,
            critical_multiplier=weapon.critical_multiplier,
            status_chance=weapon.status_chance,
            multishot=weapon.multishot,
        ),
        b,
    )
    magazine = (
        None
        if weapon.magazine_size is None
        else modded(weapon.magazine_size, Stat.MAGAZINE_CAPACITY, b)
    )
    reload = modded_time(weapon.reload_time, modded(1.0, Stat.RELOAD_SPEED, b) - 1)
    ammo_cost = attack.ammo_cost if attack.ammo_cost is not None else 1.0
    firing = Firing(
        fire_rate=weapon.fire_rate,
        charge_time=attack.charge_time,
        burst_count=attack.burst_count,
        burst_delay=attack.burst_delay,
        bow=weapon.weapon_type == "Bow",
        magazine=magazine,
        ammo_cost=ammo_cost,
        reload_time=reload,
        no_reload=weapon.no_reload,
        reload_replaces_shot=weapon.reload_replaces_shot,
    )
    rate = effective_fire_rate(firing, modded(1.0, Stat.FIRE_RATE, b))
    crit_avg = crit.average_multiplier(
        hit.critical_chance, hit.critical_multiplier, hit.crit_upgrade_chance
    )
    shot_factor = hit.multishot * crit_avg
    direct = {t: v * shot_factor for t, v in hit.damage.items()}
    per_projectile = expected_procs(hit.status_chance, proc_shares(hit.damage))
    procs = {t: p * hit.multishot for t, p in per_projectile.items() if isinstance(t, DamageType)}
    seed = dot_seed(hit.modded_base, crit_avg)
    shots = None
    if magazine is not None and ammo_cost > 0 and not weapon.no_reload:
        shots = max(1, math.floor(magazine / ammo_cost))
    return ShotModel(
        interval=1 / rate,
        shots_per_mag=shots,
        reload=reload,
        direct=direct,
        procs=procs,
        dot_tick={
            t: dot_tick(seed, t, hit.element_bonus.get(t, 0.0), 1.0, hit.status_damage)
            for t in DOT_TYPES
            if procs.get(t)
        },
        dot_ticks={t: dot_ticks(t, hit.status_duration) for t in DOT_TYPES if procs.get(t)},
        duration=BASE_DURATION_S * (1 + hit.status_duration),
        burst_dps=math.fsum(direct.values()) * rate,
    )


def enemies(scale_dps: float, seed: int) -> list[Enemy]:
    """Synthetic enemies (cost shape only): effective health spread so the fights end
    between ~0.3 s and past the 10 s cap for a gun of `scale_dps` burst DPS."""
    rng = random.Random(seed)
    out = []
    for i in range(ENEMIES):
        target_s = 0.3 * (60 ** (i / (ENEMIES - 1)))  # 0.3 s .. 18 s, log-spaced
        pool_hp = scale_dps * target_s
        shield_share = rng.choice((0.0, 0.0, 0.3, 0.6))
        out.append(
            Enemy(
                health=pool_hp * (1 - shield_share),
                shield=pool_hp * shield_share,
                armor=rng.choice((0.0, 300.0, 1500.0, 6000.0)),
                faction={t: rng.choice((0.5, 1.0, 1.0, 1.5)) for t in DamageType},
                toxin_bypass=i != 5,
            )
        )
    return out
