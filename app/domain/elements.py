"""Elemental combination (saved Damage, Elemental Damage Combinations; Calculating_Bonuses).

Primary elements combine in pairs following the mod layout: slots left to right, top row
then bottom row; the first mod of an element sets its place, later mods of the same
element add to it. Innate primary elements come last (two innate ones in Heat > Cold >
Electricity > Toxin order), unless a mod of the same element placed them earlier.
Secondary elements (innate or from a mod) are never combined further.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.effects import DamageType as D

PRIMARY = (D.HEAT, D.COLD, D.ELECTRICITY, D.TOXIN)  # also the HCET order for innate ones
COMBINED: dict[frozenset[D], D] = {
    frozenset({D.HEAT, D.COLD}): D.BLAST,
    frozenset({D.HEAT, D.ELECTRICITY}): D.RADIATION,
    frozenset({D.HEAT, D.TOXIN}): D.GAS,
    frozenset({D.COLD, D.ELECTRICITY}): D.MAGNETIC,
    frozenset({D.COLD, D.TOXIN}): D.VIRAL,
    frozenset({D.ELECTRICITY, D.TOXIN}): D.CORROSIVE,
}
ELEMENTS = frozenset(PRIMARY) | frozenset(COMBINED.values())


@dataclass(frozen=True)
class Part:
    """One contribution to an element: a mod's bonus (fraction of base damage) or an
    innate amount (absolute damage)."""

    element: D
    mod_fraction: float = 0.0
    innate: float = 0.0


def combine(mods: Sequence[Part], innate: Sequence[Part]) -> dict[D, list[Part]]:
    """Final element -> the parts that make it (each element's sum is quantized alone).

    `mods` in slot order (mod effects only); `innate` holds the weapon's own elements.
    """
    for p in [*mods, *innate]:
        if p.element not in ELEMENTS:
            raise ValueError(f"{p.element} is not an element")
    order: list[D] = []
    parts: dict[D, list[Part]] = {}
    secondary: dict[D, list[Part]] = {}
    innate_primary = sorted(
        (p for p in innate if p.element in PRIMARY), key=lambda p: PRIMARY.index(p.element)
    )
    for p in [*mods, *innate_primary]:
        if p.element not in PRIMARY:
            continue
        if p.element not in parts:
            order.append(p.element)
            parts[p.element] = []
        parts[p.element].append(p)
    for p in [*mods, *innate]:
        if p.element not in PRIMARY:
            secondary.setdefault(p.element, []).append(p)

    out: dict[D, list[Part]] = {e: list(ps) for e, ps in secondary.items()}
    for i in range(0, len(order) - 1, 2):
        a, b = order[i], order[i + 1]
        out.setdefault(COMBINED[frozenset({a, b})], []).extend(parts[a] + parts[b])
    if len(order) % 2:
        out.setdefault(order[-1], []).extend(parts[order[-1]])
    return out
