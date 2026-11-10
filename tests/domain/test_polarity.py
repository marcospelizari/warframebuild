import random
from itertools import product

import pytest

from app.domain.polarity import (
    REGULAR_SLOTS,
    Layout,
    Piece,
    Polarity,
    capacity,
    drain,
    solve,
)

M, N, V, ANY = Polarity.MADURAI, Polarity.NARAMON, Polarity.VAZARIN, Polarity.ANY


def test_matching_slot_halves_rounded_up() -> None:
    """Mod:163: Serration 14 in a Madurai slot costs 7."""
    assert drain(14, M, M) == 7
    assert drain(9, M, M) == 5
    assert drain(9, ANY, N) == 5


@pytest.mark.parametrize(
    ("base", "cost"), [(1, 1), (2, 3), (5, 6), (6, 8), (9, 11), (10, 13), (14, 18), (16, 20)]
)
def test_mismatch_adds_a_quarter_rounded_mathematically(base: int, cost: int) -> None:
    """Mod:164 ranges; in game: 9 -> 11, 5 -> 6."""
    assert drain(base, N, M) == cost


def test_capacity_with_a_catalyst() -> None:
    assert capacity(30) == 60
    assert capacity(40) == 80


def test_no_forma_when_it_fits() -> None:
    layout = solve([Piece(M, 14)] * 4, None, [M], None, 60)
    assert layout is not None and layout.forma == 0
    assert layout.used == 7 + 14 * 3


def test_forma_until_it_fits() -> None:
    mods = [Piece(M, 16)] * 4 + [Piece(N, 14)] * 4  # 120 without polarity
    layout = solve(mods, None, [], None, 60)
    assert layout is not None
    assert (layout.forma, layout.used) == (8, 4 * 8 + 4 * 7)
    assert solve([Piece(M, 16)] * 8, None, [], None, 60) is None  # 8 x 8 = 64


def test_built_in_mismatch_is_parked_in_an_empty_slot() -> None:
    layout = solve([Piece(M, 10)], None, [V, V], None, 60)
    assert layout is not None and layout.forma == 0 and layout.used == 10


def test_exilus_slot_keeps_its_polarity_or_takes_a_forma() -> None:
    kept = solve([], Piece(N, 7), [], N, 60)
    assert kept is not None and (kept.forma, kept.used) == (0, 4)
    tight = solve([Piece(M, 14)] * 8, Piece(N, 7), [M] * 8, M, 60)  # 56 + 9 > 60
    assert tight is not None and tight.forma == 1 and tight.used == 56 + 4


def _brute(mods: list[Piece], built_in: list[Polarity], cap: int) -> tuple[int, int] | None:
    """Every built-in placement (under a mod slot or in an empty slot) x every forma choice."""
    spare = REGULAR_SLOTS - len(mods)
    best: tuple[int, int] | None = None
    targets: list[int | str] = [*range(len(mods)), "empty"]
    for places in product(targets, repeat=len(built_in)):
        on_mods = [t for t in places if t != "empty"]
        if len(set(on_mods)) < len(on_mods) or places.count("empty") > spare:
            continue
        slot: list[Polarity | None] = [None] * len(mods)
        for pol, t in zip(built_in, places, strict=True):
            if t != "empty":
                slot[t] = pol  # type: ignore[index]
        for formed in product([False, True], repeat=len(mods)):
            used = sum(
                drain(m.drain, m.polarity if f else s, m.polarity)
                for m, s, f in zip(mods, slot, formed, strict=True)
            )
            key = (sum(formed), used)
            if used <= cap and (best is None or key < best):
                best = key
    return best


@pytest.mark.parametrize("seed", range(40))
def test_solver_equals_brute_force(seed: int) -> None:
    rng = random.Random(seed)
    mods = [Piece(rng.choice([M, N, V]), rng.randint(2, 16)) for _ in range(rng.randint(0, 8))]
    built_in = [rng.choice([M, N, V, ANY]) for _ in range(rng.randint(0, 3))]
    cap = rng.randint(20, 60)
    layout: Layout | None = solve(mods, None, built_in, None, cap)
    expected = _brute(mods, built_in, cap)
    assert (None if layout is None else (layout.forma, layout.used)) == expected
