"""Forma layout of a searched build (PLAN Q6/Q43, G84): mods at max rank (Q33), catalyst."""

from collections.abc import Sequence

from app.domain.polarity import Layout, Piece, capacity, solve
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
