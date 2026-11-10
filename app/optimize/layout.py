"""Slot orders of a mod set that change its elements (domain.elements: the first mod of a
primary element sets its place, elements pair in that order)."""

from collections.abc import Sequence
from itertools import permutations

from app.domain.effects import DamageType, Stat
from app.domain.elements import PRIMARY
from app.gamedata.models import Mod


def element_of(m: Mod) -> DamageType | None:
    return next(
        (
            e.damage_type
            for e in m.effects.effects
            if e.stat == Stat.ELEMENT and e.damage_type in PRIMARY
        ),
        None,
    )


def orders(mods: Sequence[Mod]) -> list[list[Mod]]:
    """One slot order per distinct pairing of the mods' primary elements (at most 3): other
    mods first, then the element mods grouped by element. Deterministic."""
    plain = sorted((m for m in mods if element_of(m) is None), key=lambda m: m.unique_name)
    groups: dict[DamageType, list[Mod]] = {}
    for m in sorted(mods, key=lambda m: m.unique_name):
        element = element_of(m)
        if element is not None:
            groups.setdefault(element, []).append(m)
    elements = sorted(groups, key=PRIMARY.index)
    seen: set[tuple[frozenset[frozenset[DamageType]], DamageType | None]] = set()
    out = []
    for order in permutations(elements):
        pairs = frozenset(frozenset(order[i : i + 2]) for i in range(0, len(order) - 1, 2))
        key = (pairs, order[-1] if len(order) % 2 else None)
        if key in seen:
            continue
        seen.add(key)
        out.append(plain + [m for e in order for m in groups[e]])
    return out
