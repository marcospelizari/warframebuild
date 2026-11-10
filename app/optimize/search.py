"""Mod search for one objective (PLAN G81, E3).

Every legal mod set is scored when they all fit the evaluation budget (`optimal`); otherwise,
from the empty build, the best-improving add / remove / swap move is taken until none helps or
the budget ends (`best_found`): adds fill the slots greedily, swaps then refine. A set is
scored at its best element pairing (`layout.orders`).
"""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Literal

from app.domain import families
from app.gamedata.models import Mod
from app.optimize.layout import orders

MAX_EVALUATIONS = 20_000  # per build (E3, G64)
REGULAR_SLOTS = 8
MAX_ORDERS = 3  # distinct pairings of up to four primary elements

Score = Callable[[list[Mod], Mod | None], float]  # regular mods in slot order, exilus mod


@dataclass(frozen=True)
class Result:
    mods: list[Mod]  # regular slots, slot order
    exilus: Mod | None
    score: float
    status: Literal["optimal", "best_found"]
    evaluations: int


class _Budget(Exception):
    pass


def search(pool: Sequence[Mod], score: Score, budget: int = MAX_EVALUATIONS) -> Result:
    """`pool`: candidate mods (`candidates.pool`), each fitting the gun."""
    s = _Search(list(pool), score, budget)
    exhaustive = _legal_upper(s.pool) * MAX_ORDERS <= budget
    try:
        if exhaustive:
            for chosen in s.all_sets():
                s.consider(chosen)
        else:
            s.improve()
    except _Budget:
        exhaustive = False
    return s.result("optimal" if exhaustive else "best_found")


def rounded(score: float) -> float:
    """Scores compare after rounding to 9 significant digits (G16)."""
    return float(f"{score:.9g}")


def _legal_upper(pool: Sequence[Mod]) -> int:
    """Mod sets within the slots, families ignored (an upper bound on the legal ones)."""
    regular = sum(1 for m in pool if not m.exilus)
    exilus = len(pool) - regular
    return sum(
        comb(regular, a) * comb(exilus, b)
        for a in range(REGULAR_SLOTS + 1)
        for b in range(REGULAR_SLOTS + 2 - a)
    )


class _Search:
    def __init__(self, pool: list[Mod], score: Score, budget: int) -> None:
        self.pool = sorted(pool, key=lambda m: m.unique_name)
        self.score, self.budget = score, budget
        self.evaluations = 0
        self.cache: dict[frozenset[int], tuple[float, list[Mod], Mod | None]] = {}
        self.best: tuple[float, tuple[str, ...], frozenset[int]] | None = None

    def all_sets(self) -> Iterator[frozenset[int]]:
        for size in range(REGULAR_SLOTS + 2):
            for chosen in combinations(range(len(self.pool)), size):
                if self.legal(frozenset(chosen)):
                    yield frozenset(chosen)

    def legal(self, chosen: frozenset[int]) -> bool:
        mods = [self.pool[i] for i in chosen]
        if len(mods) > REGULAR_SLOTS + 1 or sum(not m.exilus for m in mods) > REGULAR_SLOTS:
            return False
        return not families.clashes((m.unique_name, m.family) for m in mods)

    def consider(self, chosen: frozenset[int]) -> float:
        value = self.value(chosen)
        key = (rounded(value), self._names(chosen), chosen)
        if self.best is None or _better(key, self.best):
            self.best = key
        return value

    def value(self, chosen: frozenset[int]) -> float:
        if chosen in self.cache:
            return self.cache[chosen][0]
        mods = [self.pool[i] for i in sorted(chosen)]
        exilus = None
        if len(mods) > REGULAR_SLOTS:  # one exilus-capable mod moves to the exilus slot
            exilus = max((m for m in mods if m.exilus), key=lambda m: m.unique_name)
            mods = [m for m in mods if m is not exilus]
        best: tuple[float, list[Mod]] | None = None
        for order in orders(mods):
            if self.evaluations >= self.budget:
                raise _Budget
            self.evaluations += 1
            v = self.score(order, exilus)
            if best is None or rounded(v) > rounded(best[0]):
                best = (v, order)
        assert best is not None
        self.cache[chosen] = (best[0], best[1], exilus)
        return best[0]

    def improve(self) -> None:
        current: frozenset[int] = frozenset()
        self.consider(current)
        while True:
            moves = [current | {i} for i in range(len(self.pool)) if i not in current]
            moves += [current - {i} for i in current]
            moves += [
                (current - {i}) | {j}
                for i in sorted(current)
                for j in range(len(self.pool))
                if j not in current
            ]
            here = (rounded(self.value(current)), self._names(current), current)
            step = here
            for chosen in moves:
                if not self.legal(chosen):
                    continue
                key = (rounded(self.consider(chosen)), self._names(chosen), chosen)
                if _better(key, step):
                    step = key
            if step is here:
                return
            current = step[2]

    def result(self, status: Literal["optimal", "best_found"]) -> Result:
        assert self.best is not None
        value, order, exilus = self.cache[self.best[2]]
        return Result(order, exilus, value, status, self.evaluations)

    def _names(self, chosen: frozenset[int]) -> tuple[str, ...]:
        return tuple(sorted(self.pool[i].unique_name for i in chosen))


def _better(
    a: tuple[float, tuple[str, ...], frozenset[int]],
    b: tuple[float, tuple[str, ...], frozenset[int]],
) -> bool:
    """Higher rounded score; ties by the sorted uniqueNames (G16)."""
    return a[0] > b[0] or (a[0] == b[0] and a[1] < b[1])
