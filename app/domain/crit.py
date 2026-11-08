"""Critical tiers (saved Critical_Hit: Critical Tiers, Critical Headshots; PLAN G9/C1).

Crit chance `c` gives tier floor(c) or the next tier with chance frac(c): at 100% every
hit crits, above 100% a hit is yellow or orange, never a non-crit. Tier t multiplies by
`1 + t x (CD - 1)`; on a body part with the critical-headshot flag the crit damage is
doubled: `1 + t x (2 CD - 1)` (the headshot multiplier itself is applied by the caller).
Vigilante set pieces give a chance to raise a crit's tier by one (only crits, tier >= 1).
"""

import math


def tiers(crit_chance: float, upgrade_chance: float = 0.0) -> dict[int, float]:
    """Probability of each crit tier (0 = non-crit) for one hit."""
    if crit_chance < 0 or not 0 <= upgrade_chance <= 1:
        raise ValueError("crit chance must be >= 0 and upgrade chance within 0..1")
    low = math.floor(crit_chance)
    frac = crit_chance - low
    raw = {low: 1 - frac, low + 1: frac}
    out: dict[int, float] = {}
    for tier, p in raw.items():
        if p <= 0:
            continue
        if tier >= 1 and upgrade_chance:
            out[tier] = out.get(tier, 0.0) + p * (1 - upgrade_chance)
            out[tier + 1] = out.get(tier + 1, 0.0) + p * upgrade_chance
        else:
            out[tier] = out.get(tier, 0.0) + p
    return out


def tier_multiplier(tier: int, crit_damage: float, headcrit: bool = False) -> float:
    return 1 + tier * ((2 * crit_damage if headcrit else crit_damage) - 1)


def average_multiplier(
    crit_chance: float, crit_damage: float, upgrade_chance: float = 0.0, headcrit: bool = False
) -> float:
    """Expected crit multiplier of one hit."""
    return math.fsum(
        p * tier_multiplier(t, crit_damage, headcrit)
        for t, p in tiers(crit_chance, upgrade_chance).items()
    )


def non_crit_chance(crit_chance: float) -> float:
    """Chance a hit does not crit; 0 from 100% crit chance on (C1)."""
    return max(0.0, 1 - crit_chance)
