"""Status effects (G8): proc types beyond the damage types.

A damage-type proc is named by its `DamageType`. Crowd-control effects deal no damage;
some still count as a status type on the target (Condition Overload-style bonuses,
saved `Condition_Overload_(Mechanic)`: Knockdown, Lifted). Also the proc, DoT and
Blast rules (sources in each section).
"""

import math
from collections import deque
from collections.abc import Mapping, Sequence
from enum import StrEnum

from app.domain.effects import DamageType, FireRateBoost


class CrowdControl(StrEnum):
    KNOCKDOWN = "knockdown"
    LIFTED = "lifted"
    RAGDOLL = "ragdoll"
    STAGGER = "stagger"
    BIG_STAGGER = "big_stagger"
    BLIND = "blind"
    STUN = "stun"


# A guaranteed proc an attack applies regardless of status chance (saved Status_Effect,
# Forced Procs).
ForcedProc = DamageType | CrowdControl


# ---------- proc chances (saved Status_Effect: Status Chance, Damage Distribution) ----------


def proc_shares(damage: Mapping[DamageType, float]) -> dict[DamageType, float]:
    """Chance of each type when a hit procs: its damage / total damage."""
    total = math.fsum(v for v in damage.values() if v > 0)
    return {t: v / total for t, v in damage.items() if v > 0} if total else {}


def expected_procs(
    status_chance: float, shares: Mapping[DamageType, float], forced: Sequence[ForcedProc] = ()
) -> dict[ForcedProc, float]:
    """Expected procs of each type on one projectile: status chance split by damage share
    (above 100% extra procs are drawn independently), plus forced procs."""
    out: dict[ForcedProc, float] = {t: status_chance * s for t, s in shares.items()}
    for proc in forced:
        out[proc] = out.get(proc, 0.0) + 1.0
    return out


def chance_of_at_least_one(status_chance: float, share: float) -> float:
    """Chance one projectile gets at least one proc of a type with damage share `share`:
    floor(chance) guaranteed draws plus one more with the remaining chance."""
    draws = math.floor(status_chance)
    extra = status_chance - draws
    return 1 - (1 - share) ** draws * (1 - extra * share)


def combined_chance(chances: Sequence[float]) -> float:
    """Independent sources of the same forced proc that apply it at most once per damage
    instance (Hunter Munitions + Internal Bleeding: `1 - (1 - a)(1 - b)`, saved
    Hunter_Munitions / Internal_Bleeding)."""
    miss = 1.0
    for p in chances:
        miss *= 1 - min(1.0, max(0.0, p))
    return 1 - miss


def boosted(value: float, boost: FireRateBoost | None, fire_rate: float) -> float:
    """Internal Bleeding: x2 while the modded fire rate is strictly below 2.5."""
    return value * boost.factor if boost and fire_rate < boost.below else value


# How long one proc stays on the target (saved Status_Effect: Status Duration table; Void and
# Tau from the damage-type table); x (1 + status duration). Knockdown and Lifted count as
# status types too (same page) but it gives them no duration: not listed.
STATUS_S: dict[DamageType, float] = {
    DamageType.IMPACT: 6.0,
    DamageType.PUNCTURE: 10.0,  # table (Status_Effect:256); a patch note there says 6 s (:1048)
    DamageType.SLASH: 6.0,
    DamageType.COLD: 6.0,
    DamageType.ELECTRICITY: 6.0,
    DamageType.HEAT: 6.0,
    DamageType.TOXIN: 6.0,
    DamageType.BLAST: 1.5,
    DamageType.CORROSIVE: 8.0,
    DamageType.GAS: 6.0,
    DamageType.MAGNETIC: 6.0,
    DamageType.RADIATION: 12.0,
    DamageType.VIRAL: 6.0,
    DamageType.VOID: 3.0,
    DamageType.TAU: 8.0,
}


# ---------- damage over time (saved Damage/Calculation, Damage Over Time) ----------

DOT_COEFFICIENT: dict[DamageType, float] = {
    DamageType.SLASH: 0.35,
    DamageType.HEAT: 0.5,
    DamageType.ELECTRICITY: 0.5,
    DamageType.TOXIN: 0.5,
    DamageType.GAS: 0.5,
}
BASE_DURATION_S = 6.0  # one tick per second (Status_Effect, Status Damage)
# Slash, Heat, Toxin tick first after 1 s; Electricity and Gas at once (Status_Effect).
FIRST_TICK_S: dict[DamageType, float] = {
    DamageType.SLASH: 1.0,
    DamageType.HEAT: 1.0,
    DamageType.TOXIN: 1.0,
    DamageType.ELECTRICITY: 0.0,
    DamageType.GAS: 0.0,
}


def dot_seed(modded_base: float, hit_multiplier: float, faction: float = 1.0) -> float:
    """Damage seed of one proc: the attack's modded base damage (not quantized, no element
    or physical bonuses) x the multipliers of the hit that applied it (crit, body part,
    sniper combo; saved Damage_over_Time, DoT Damage Scaling) x faction."""
    return modded_base * hit_multiplier * faction


def dot_tick(
    seeds: float,
    damage_type: DamageType,
    element_bonus: float = 0.0,
    faction: float = 1.0,
    status_damage: float = 0.0,
) -> float:
    """`(sum of seeds + 1) x C x M`: Heat/Electricity/Gas pool their seeds into one tick,
    Slash and Toxin stacks tick separately (one seed each). M = (1 + element bonus of the
    type's own mods, `element_bonuses`; none for Slash) x faction (a second time) x
    (1 + status damage)."""
    coefficient = DOT_COEFFICIENT[damage_type]
    element = 1.0 if damage_type == DamageType.SLASH else 1 + element_bonus
    return (seeds + 1) * coefficient * element * faction * (1 + status_damage)


def dot_ticks(damage_type: DamageType, duration_bonus: float) -> int:
    """Ticks per proc over 6 s x (1 + status duration), one per second.

    After a 1 s delay (Slash, Heat, Toxin): `floor(duration - 1) + 1` (saved
    Damage_over_Time; 6 s -> 6, Hunter Track 11.4 s -> 11 as on Hunter_Munitions). From
    0 s (Electricity, Gas): Status_Effect's table shows ticks at 0..5 s for 6 s, so
    `ceil(duration)`; the formula's `+1` would give 7 (assumption, stated)."""
    duration = BASE_DURATION_S * (1 + duration_bonus)
    if duration <= 0:
        return 0
    if FIRST_TICK_S[damage_type] > 0:
        return max(0, math.floor(duration - FIRST_TICK_S[damage_type] + 1e-9) + 1)
    return math.ceil(duration - 1e-9)


def heat_ticks(
    procs: Sequence[tuple[float, float, float]],
    tick_factor: float,
    life: float,
    refreshed: bool,
    until: float,
) -> list[tuple[float, float]]:
    """Heat's one pooled tick per second (saved Heat_Damage:66; Damage/Calculation, DoT):
    `(sum of live seeds + 1) x C x M`, from 1 s after the first proc. `procs`: (time,
    expected seeds, expected procs) per hit; `tick_factor` = C x M. Each proc refreshes all
    stacks, so with `refreshed` every earlier proc stays live; otherwise each lasts `life`.
    Below one expected live proc the +1 scales with it."""
    if not procs:
        return []
    out = []
    tick = procs[0][0] + FIRST_TICK_S[DamageType.HEAT]
    last = procs[-1][0] + life
    while tick <= min(last, until):
        live = [(s, p) for t, s, p in procs if t < tick and (refreshed or t > tick - life)]
        if live:
            seeds = math.fsum(s for s, _ in live)
            count = math.fsum(p for _, p in live)
            out.append((tick, (seeds + min(1.0, count)) * tick_factor))
        tick += 1.0
    return out


# ---------- Blast (saved Blast_Damage; Damage/Calculation: stack-and-detonate) ----------

BLAST_CAP = 10
BLAST_CAP_BOSS = 4
BLAST_STACK_S = 1.5  # fuse, x (1 + status duration) (Blast_Damage:21, :64)
BLAST_PROC = 0.3  # share of modded base damage per stack (Blast_Damage:21, :36-41)
BLAST_DETONATION = 3.0


def blast_proc(
    modded_base: float, hit_multiplier: float, faction: float = 1.0, status_damage: float = 0.0
) -> float:
    """What one stack deals to its target: 0.3 x modded base damage (no element or physical
    bonuses) x the hit's crit and body part (`hit_multiplier`, faction already in it) x
    faction again x (1 + status damage) (Blast_Damage:30-44; at least 1, Calculation:644)."""
    return max(1.0, BLAST_PROC * modded_base * hit_multiplier * faction * (1 + status_damage))


def blast_hits(
    stacks: Sequence[tuple[float, float, float]], fuse: float, cap: int = BLAST_CAP
) -> list[tuple[float, float]]:
    """Blast damage on the target: (time, expected stacks, one stack's damage) per hit ->
    (time, damage). Each stack hits its target when its fuse runs out; at `cap` active stacks
    they all hit at once. The 3x radial burst never hits the detonating target
    (Blast_Damage:23, :59), so the target takes the same total, only sooner."""
    out: list[tuple[float, float]] = []
    active: deque[tuple[float, float, float]] = deque()
    for t, n, damage in stacks:
        while active and active[0][0] + fuse <= t:
            at, sn, sd = active.popleft()
            out.append((at + fuse, sn * sd))
        active.append((t, n, damage))
        if math.fsum(s[1] for s in active) >= cap:
            out.append((t, math.fsum(sn * sd for _, sn, sd in active)))
            active.clear()
    out += [(at + fuse, sn * sd) for at, sn, sd in active]
    return out


def blast_detonation(stack_hits: Sequence[float]) -> float:
    """The radial burst on *other* enemies in 5 m: 3 x the stacks' hit damage (not scored:
    the detonating target never takes it, Blast_Damage:23)."""
    return BLAST_DETONATION * math.fsum(stack_hits)
