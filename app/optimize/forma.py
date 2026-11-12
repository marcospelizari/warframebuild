"""Forma layout of a searched build (PLAN Q6/Q43, G84): mods at max rank (Q33), catalyst."""

import math
from collections.abc import Sequence

from app.domain.polarity import Layout, Piece, Slot, capacity, solve
from app.gamedata.builds import Forma, FormaSlot
from app.gamedata.models import Mod, Weapon


def piece(m: Mod) -> Piece:
    """Drain at max rank = base drain + max rank (fusion limit)."""
    return Piece(m.polarity, m.base_drain + m.fusion_limit)


def forma_layout(weapon: Weapon, mods: Sequence[Mod], exilus: Mod | None) -> Layout | None:
    """Fewest forma that fit; None: no layout fits (the build is flagged, Q6)."""
    return solve(
        [piece(m) for m in mods],
        piece(exilus) if exilus else None,
        weapon.polarities,
        weapon.exilus_polarity,
        capacity(weapon.max_rank),
    )


def fits(weapon: Weapon, mods: Sequence[Mod], exilus: Mod | None) -> bool:
    """Some forma layout fits: forma can match every slot (no gun mod is Umbra), so the
    least drain is each mod at half, rounded up (G84)."""
    equipped = [*mods, *([exilus] if exilus else [])]
    return sum(math.ceil(piece(m).drain / 2) for m in equipped) <= capacity(weapon.max_rank)


def stored_forma(layout: Layout | None) -> Forma | None:
    """The layout as stored and served; None: no layout fits."""
    if layout is None:
        return None

    def slot(s: Slot) -> FormaSlot:
        return FormaSlot(polarity=s.polarity, forma=s.forma, drain=s.drain)

    return Forma(
        regular=[slot(s) for s in layout.regular],
        exilus=slot(layout.exilus) if layout.exilus else None,
        forma=layout.forma,
        used=layout.used,
        capacity=layout.capacity,
    )
