"""One attack with its active bonuses -> modded hit (saved Damage/Calculation: Total Damage,
Average Shot; Calculating_Bonuses).

Callers pass the effects active for the evaluated case, in slot order (elements depend on
it), each with its resolved value (`stats.value_for`). Conditional bonuses, stacks, status,
DoT and fire rate are steps 4c and 8.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from app.domain import crit
from app.domain.damage import composition, element_bonuses, scaled
from app.domain.direct_bonus import DirectBonus, damage_factor
from app.domain.effects import DamageType, Effect, Faction, Stat
from app.domain.elements import Part
from app.domain.stats import modded

Bonus = tuple[Effect, float]  # effect and its resolved value


@dataclass(frozen=True)
class AttackStats:
    damage: Mapping[DamageType, float]
    critical_chance: float
    critical_multiplier: float
    status_chance: float
    multishot: float


@dataclass(frozen=True)
class ModdedHit:
    damage: dict[DamageType, float]  # one projectile, quantized, damage bonuses applied
    critical_chance: float
    critical_multiplier: float
    status_chance: float  # per projectile
    multishot: float  # expected projectiles per shot
    faction_multiplier: dict[Faction, float]  # Bane-style factor per faction (1 if none)
    crit_upgrade_chance: float  # Vigilante set (crit_tier_upgrade)
    unscaled: dict[DamageType, float]  # quantized composition before damage multipliers
    base_total: float  # the attack's unmodded base damage total
    modded_base: float  # base damage total x damage bonuses: the DoT seed before crit
    damage_multiplier: float  # Serration group x separate damage factors
    element_bonus: dict[DamageType, float]  # summed bonus of the mods of each element (DoT)
    status_damage: float  # bonus (Elementalist), additive group, separate factor on DoT
    status_duration: float  # bonus (Hunter Track +0.9)
    direct_bonus: float | None = None  # Galvanized-style bonus once applied

    @property
    def projectile_damage(self) -> float:
        return math.fsum(self.damage.values())

    @property
    def arsenal_total(self) -> float:
        """Average non-crit damage per shot without faction bonus, as the arsenal shows."""
        return self.projectile_damage * self.multishot

    def average_shot(
        self, faction: Faction | None = None, headshot: float = 1.0, headcrit: bool = False
    ) -> float:
        """Expected damage of one shot when every projectile hits (direct damage only).

        `headshot`: the body part's multiplier (1 = body); `headcrit`: the part has the
        critical-headshot flag (saved Critical_Hit).
        """
        factor = self.faction_multiplier.get(faction, 1.0) if faction else 1.0
        crit_avg = crit.average_multiplier(
            self.critical_chance, self.critical_multiplier, self.crit_upgrade_chance, headcrit
        )
        return self.arsenal_total * factor * headshot * crit_avg


def modded_hit(
    base: AttackStats,
    bonuses: Sequence[Bonus],
    bonus_element: tuple[DamageType, float] | None = None,
) -> ModdedHit:
    elements: list[Part] = []
    physical: dict[DamageType, float] = {}
    for e, v in bonuses:
        if e.damage_type is None:
            continue
        if e.stat == Stat.ELEMENT:
            elements.append(Part(e.damage_type, v))
        elif e.stat == Stat.PHYSICAL:
            physical[e.damage_type] = physical.get(e.damage_type, 0.0) + v
    quantized = composition(base.damage, elements, physical, bonus_element)
    damage_multiplier = modded(1.0, Stat.DAMAGE, bonuses)
    factions = {e.faction for e, _ in bonuses if e.stat == Stat.FACTION_DAMAGE and e.faction}
    return ModdedHit(
        damage=scaled(quantized, damage_multiplier),
        critical_chance=modded(base.critical_chance, Stat.CRITICAL_CHANCE, bonuses),
        critical_multiplier=modded(base.critical_multiplier, Stat.CRITICAL_DAMAGE, bonuses),
        status_chance=modded(base.status_chance, Stat.STATUS_CHANCE, bonuses),
        multishot=modded(base.multishot, Stat.MULTISHOT, bonuses),
        faction_multiplier={
            f: modded(1.0, Stat.FACTION_DAMAGE, [(e, v) for e, v in bonuses if e.faction == f])
            for f in sorted(factions)
        },
        crit_upgrade_chance=min(
            1.0, math.fsum(v for e, v in bonuses if e.stat == Stat.CRIT_TIER_UPGRADE)
        ),
        unscaled=quantized,
        base_total=math.fsum(base.damage.values()),
        modded_base=math.fsum(base.damage.values()) * damage_multiplier,
        damage_multiplier=damage_multiplier,
        element_bonus=element_bonuses(elements),
        status_damage=modded(1.0, Stat.STATUS_DAMAGE, bonuses) - 1,
        status_duration=modded(1.0, Stat.STATUS_DURATION, bonuses) - 1,
    )


def with_direct_bonus(hit: ModdedHit, behaviour: DirectBonus, direct: float) -> ModdedHit:
    """The hit with a Galvanized-style bonus applied the attack's way.

    `direct` is the summed bonus of every CO-like source: they stack additively with each
    other (saved Condition_Overload_(Mechanic), Math), so call this once per hit, never
    once per source: a second call raises. The DoT seed takes the same factor: procs are
    generated from the bonused hit (same page, Blast/Electricity/Gas line; G63 extends it
    to Heat, Slash and Toxin as an assumption). Attack-specific DoT parts (Tysis, Stinger)
    are separate attacks with behaviour `none`.
    """
    if hit.direct_bonus is not None:
        raise ValueError("direct bonus already applied: pass the summed bonus once")
    factor = damage_factor(behaviour, hit.damage_multiplier, direct)
    return replace(
        hit,
        direct_bonus=direct,
        damage=scaled(hit.unscaled, factor),
        modded_base=hit.base_total * factor,
        damage_multiplier=factor,
    )
