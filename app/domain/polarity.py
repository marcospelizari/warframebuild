"""Mod drain, capacity and the forma solver (PLAN Q6/Q43, G84; saved Mod: Installation,
Polarity).

Drain at max rank = base drain + max rank. A matching slot halves it (rounded up); a slot of
another polarity adds a quarter, rounded mathematically (`Mod`:164, checked in game). Capacity
with a catalyst = 2 x the item's max rank. Built-in slot positions are not known, so the
solver places them; forma (regular only) adds or replaces a slot polarity.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations

REGULAR_SLOTS = 8


class Polarity(StrEnum):
    MADURAI = "madurai"
    NARAMON = "naramon"
    VAZARIN = "vazarin"
    ANY = "any"  # matches every polarity but Umbra (Polarity:17-18)


def matches(slot: Polarity, mod: Polarity) -> bool:
    return slot == mod or slot == Polarity.ANY


def drain(base: int, slot: Polarity | None, mod: Polarity) -> int:
    """Drain of a mod with drain `base` (at its rank) in a slot of polarity `slot`."""
    if slot is None:
        return base
    if matches(slot, mod):
        return math.ceil(base / 2)
    return base + math.floor(base / 4 + 0.5)  # halves round up: 2 -> +1, 6 -> +2, 10 -> +3


def capacity(max_rank: int) -> int:
    """With an Orokin Catalyst: double the max rank (Mod:156)."""
    return 2 * max_rank


@dataclass(frozen=True)
class Piece:
    polarity: Polarity
    drain: int  # at max rank, before polarity


@dataclass(frozen=True)
class Slot:
    polarity: Polarity | None
    forma: bool  # polarity added or replaced by a forma
    drain: int  # 0 when empty


@dataclass(frozen=True)
class Layout:
    regular: list[Slot]  # one per mod in the given order, then the empty slots
    exilus: Slot | None  # None: no exilus mod
    forma: int
    used: int
    capacity: int


def solve(
    mods: Sequence[Piece],
    exilus: Piece | None,
    built_in: Sequence[Polarity],
    exilus_built_in: Polarity | None,
    cap: int,
) -> Layout | None:
    """Fewest forma that fit `cap`, then least drain; None if no layout fits. `built_in`: the
    item's regular slot polarities (positions free)."""
    if len(mods) > REGULAR_SLOTS or len(built_in) > REGULAR_SLOTS:
        raise ValueError("at most 8 regular slots")
    ex_options = _exilus_options(exilus, exilus_built_in)
    best: Layout | None = None
    for regular in _regular_options(list(mods), list(built_in)):
        for ex in ex_options:
            used = sum(s.drain for s in regular) + (ex.drain if ex else 0)
            if used > cap:
                continue
            forma = sum(s.forma for s in regular) + (1 if ex and ex.forma else 0)
            layout = Layout(regular, ex, forma, used, cap)
            if best is None or (forma, used) < (best.forma, best.used):
                best = layout
    return best


def _exilus_options(piece: Piece | None, built_in: Polarity | None) -> list[Slot | None]:
    if piece is None:
        return [None]
    keep = Slot(built_in, False, drain(piece.drain, built_in, piece.polarity))
    if built_in is not None and matches(built_in, piece.polarity):
        return [keep]
    return [keep, Slot(piece.polarity, True, drain(piece.drain, piece.polarity, piece.polarity))]


def _regular_options(mods: list[Piece], built_in: list[Polarity]) -> list[list[Slot]]:
    """Per forma set: built-ins first match their own polarity on the highest drains; the
    rest go to empty slots, then under forma'd mods (replaced), then under the mods whose
    mismatch costs least."""
    slots: list[Slot | None] = [None] * len(mods)
    left = list(built_in)
    for i in sorted(range(len(mods)), key=lambda i: (-mods[i].drain, i)):
        own = next((p for p in left if matches(p, mods[i].polarity)), None)
        if own is not None:
            left.remove(own)
            slots[i] = Slot(own, False, drain(mods[i].drain, own, mods[i].polarity))
    open_ = [i for i in range(len(mods)) if slots[i] is None]
    spare = REGULAR_SLOTS - len(mods)
    out = []
    for n in range(len(open_) + 1):
        for formed in combinations(open_, n):
            row = list(slots)
            for i in formed:
                p = mods[i].polarity
                row[i] = Slot(p, True, drain(mods[i].drain, p, p))
            excess = left[spare:]  # built-ins not parked in empty slots
            excess = excess[len(formed) :]  # replaced by the forma'd mods
            rest = sorted(
                (i for i in open_ if i not in formed), key=lambda i: (_penalty(mods[i].drain), i)
            )
            if len(excess) > len(rest):
                continue
            for pol, i in zip(excess, rest, strict=False):
                row[i] = Slot(pol, False, drain(mods[i].drain, pol, mods[i].polarity))
            for i in open_:
                if row[i] is None:
                    row[i] = Slot(None, False, mods[i].drain)
            empties = [Slot(p, False, 0) for p in left[:spare]]
            empties += [Slot(None, False, 0)] * (spare - len(empties))
            out.append([s for s in row if s is not None] + empties)
    return out


def _penalty(base: int) -> int:
    return math.floor(base / 4 + 0.5)
