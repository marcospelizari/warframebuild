"""Damage composition of one hit (saved Damage/Calculation, Quantization; Calculating_Bonuses).

Steps: physical bonuses scale the base's own Impact/Puncture/Slash; elements add a share
of the full base damage and combine (`elements.combine`); every resulting type is
quantized to 1/32 of the attack's base damage (combined elements as one sum). Damage
bonuses (Serration group), faction bonuses and other multipliers only scale the quantized
values, so they are applied after (`scaled`).
"""

import math
from collections.abc import Mapping, Sequence

from app.domain.effects import PHYSICAL_TYPES, DamageType
from app.domain.elements import ELEMENTS, Part, combine

QUANTUM = 32


def quantize(value: float, base_total: float) -> float:
    """Nearest multiple of base_total / 32, halves rounded away from zero."""
    scale = base_total / QUANTUM
    return math.copysign(math.floor(abs(value) / scale + 0.5) * scale, value)


def composition(
    base: Mapping[DamageType, float],
    element_mods: Sequence[Part],
    physical_bonus: Mapping[DamageType, float],
    bonus_element: tuple[DamageType, float] | None = None,
) -> dict[DamageType, float]:
    """Quantized damage per type of one hit before damage multipliers.

    `base`: the attack's unmodded damage per type; `element_mods`: mod element bonuses in
    slot order (fractions of the base total); `physical_bonus`: summed bonus per physical
    type (Piercing Caliber +120% -> {puncture: 1.2}), with no effect on a type the base
    lacks. `bonus_element`: a Kuva/Tenet progenitor element and its share of the base total
    (60% assumed, Q29); it counts as an innate element (saved Damage: two innate primaries
    combine last, in Heat > Cold > Electricity > Toxin order).
    """
    total = math.fsum(base.values())
    if total <= 0:
        return {}
    unknown = set(physical_bonus) - PHYSICAL_TYPES
    if unknown:
        raise ValueError(f"physical bonus for non-physical types {sorted(unknown)}")
    raw: dict[DamageType, float] = {}
    innate: list[Part] = []
    for damage_type, value in base.items():
        if damage_type in ELEMENTS:
            innate.append(Part(damage_type, innate=value))
        else:
            raw[damage_type] = value * (1 + physical_bonus.get(damage_type, 0.0))
    if bonus_element is not None:
        element, share = bonus_element
        if element not in ELEMENTS:
            raise ValueError(f"bonus element {element} is not an element")
        innate.append(Part(element, innate=share * total))
    for element, parts in combine(element_mods, innate).items():
        raw[element] = math.fsum(p.mod_fraction * total + p.innate for p in parts)
    out = {t: quantize(v, total) for t, v in raw.items()}
    return {t: v for t, v in sorted(out.items()) if v}


def scaled(composition: Mapping[DamageType, float], factor: float) -> dict[DamageType, float]:
    return {t: v * factor for t, v in composition.items()}
