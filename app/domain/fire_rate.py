"""Effective fire rate and time spent shooting (saved Damage/Calculation: Average Burst DPS,
Average Sustained DPS; saved Fire_Rate).

Per attack: a charge time means the charge formula, a burst count the burst formula,
otherwise the modded fire rate (Auto, Semi, Duplex, Held; Auto-Spool assumed fully spooled;
ACTIVE detonation guns assumed the same). `rate_factor` is the fire-rate multiplier from
mods (`stats.modded(1, FIRE_RATE, ...)`): it scales the fire rate and divides the charge
time (at most 10x the base charge, Fire_Rate) and the burst delay (only when it speeds up:
"Burst Delay is not affected by net negative Fire Rate bonuses").
"""

from dataclasses import dataclass

CHARGE_CAP = 10  # charge time never exceeds 10x its base (Fire_Rate)


@dataclass(frozen=True)
class Firing:
    fire_rate: float | None  # base; None = no delay between shots (Lanka)
    charge_time: float | None  # base
    burst_count: int | None
    burst_delay: float | None  # base
    bow: bool  # bows: rate = 1 / (charge + reload), Fire_Rate
    magazine: float | None  # modded; None = no magazine
    ammo_cost: float  # ammo per shot; 0 = the attack uses no ammo
    reload_time: float  # modded
    no_reload: bool  # Epitaph
    reload_replaces_shot: bool  # Vectis


def effective_fire_rate(f: Firing, rate_factor: float) -> float:
    if rate_factor <= 0:
        return 0.0
    rate = f.fire_rate * rate_factor if f.fire_rate is not None else None
    if f.charge_time:
        charge = min(f.charge_time / rate_factor, CHARGE_CAP * f.charge_time)
        if f.bow:
            return 1 / (charge + f.reload_time)
        return 1 / (charge + (1 / rate if rate else 0.0))
    if rate is None:
        raise ValueError("no fire rate and no charge time")
    if f.burst_count and f.burst_count > 1:
        delay = (f.burst_delay or 0.0) / max(rate_factor, 1.0)
        return f.burst_count / (1 / rate + (f.burst_count - 1) * delay)
    return rate


def shooting_share(f: Firing, effective_rate: float) -> float:
    """Share of time spent shooting: sustained DPS = burst DPS x this."""
    if f.no_reload or f.magazine is None or f.ammo_cost <= 0 or (f.bow and f.charge_time):
        return 1.0  # no reload, or the bow formula already holds it
    shots = f.magazine / f.ammo_cost
    if shots <= 0:
        return 0.0
    denominator = effective_rate * f.reload_time + shots
    if f.reload_replaces_shot:
        denominator -= 1
    return min(1.0, shots / denominator) if denominator > 0 else 1.0
