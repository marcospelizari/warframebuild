"""Build search for one objective (PLAN G81, E3).

A build = a mod set plus one option per choice slot (the arcane, each Incarnon EVO tier).
Every legal build is scored when they all fit the evaluation budget (`optimal`); otherwise,
from the empty build, the best-improving move (add / remove / swap a mod, change one choice)
is taken until none helps or the budget ends (`best_found`): adds fill the slots greedily,
swaps then refine. A mod set is scored at its best element pairing (`layout.orders`).
"""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from itertools import combinations, product
from math import comb, prod
from typing import Literal, Protocol

from app.domain import families
from app.gamedata.models import Mod
from app.optimize.layout import orders

MAX_EVALUATIONS = 20_000  # per build (E3, G64)
REGULAR_SLOTS = 8
MAX_ORDERS = 3  # distinct pairings of up to four primary elements


class Named(Protocol):
    @property
    def name(self) -> str: ...


Option = Named | None  # None: nothing chosen in that slot
# Regular mods in slot order, the exilus mod, one option per choice slot.
Score = Callable[[list[Mod], Mod | None, tuple[Option, ...]], float]
State = tuple[frozenset[int], tuple[int, ...]]  # pool indices, option index per slot


@dataclass(frozen=True)
class Result:
    mods: list[Mod]  # regular slots, slot order
    exilus: Mod | None
    picks: tuple[Option, ...]  # one per choice slot
    score: float
    status: Literal["optimal", "best_found"]
    evaluations: int


class _Budget(Exception):
    pass


def search(
    pool: Sequence[Mod],
    score: Score,
    budget: int = MAX_EVALUATIONS,
    choices: Sequence[Sequence[Option]] = (),
) -> Result:
    """`pool`: candidate mods (`candidates.pool`), each fitting the gun; `choices`: the
    options of each choice slot (include None when the slot may stay empty)."""
    s = _Search(list(pool), score, budget, [list(c) for c in choices])
    total = _legal_upper(s.pool) * prod(len(c) for c in s.choices) * MAX_ORDERS
    exhaustive = total <= budget
    try:
        if exhaustive:
            for state in s.all_states():
                s.consider(state)
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


Key = tuple[float, tuple[str, ...], State]


class _Search:
    def __init__(
        self, pool: list[Mod], score: Score, budget: int, choices: list[list[Option]]
    ) -> None:
        if any(not c for c in choices):
            raise ValueError("every choice slot needs an option")
        self.pool = sorted(pool, key=lambda m: m.unique_name)
        self.score, self.budget, self.choices = score, budget, choices
        self.evaluations = 0
        self.cache: dict[State, tuple[float, list[Mod], Mod | None]] = {}
        self.best: Key | None = None

    def all_states(self) -> Iterator[State]:
        picks = list(product(*(range(len(c)) for c in self.choices)))
        for size in range(REGULAR_SLOTS + 2):
            for chosen in combinations(range(len(self.pool)), size):
                if self.legal(frozenset(chosen)):
                    for p in picks:
                        yield frozenset(chosen), p

    def legal(self, chosen: frozenset[int]) -> bool:
        mods = [self.pool[i] for i in chosen]
        if len(mods) > REGULAR_SLOTS + 1 or sum(not m.exilus for m in mods) > REGULAR_SLOTS:
            return False
        return not families.clashes((m.unique_name, m.family) for m in mods)

    def consider(self, state: State) -> float:
        value = self.value(state)
        key = self.key(state)
        if self.best is None or _better(key, self.best):
            self.best = key
        return value

    def key(self, state: State) -> Key:
        return (rounded(self.value(state)), self._names(state), state)

    def value(self, state: State) -> float:
        if state in self.cache:
            return self.cache[state][0]
        chosen, picks = state
        mods = [self.pool[i] for i in sorted(chosen)]
        exilus = None
        if len(mods) > REGULAR_SLOTS:  # one exilus-capable mod moves to the exilus slot
            exilus = max((m for m in mods if m.exilus), key=lambda m: m.unique_name)
            mods = [m for m in mods if m is not exilus]
        options = tuple(c[i] for c, i in zip(self.choices, picks, strict=True))
        best: tuple[float, list[Mod]] | None = None
        for order in orders(mods):
            if self.evaluations >= self.budget:
                raise _Budget
            self.evaluations += 1
            v = self.score(order, exilus, options)
            if best is None or rounded(v) > rounded(best[0]):
                best = (v, order)
        assert best is not None
        self.cache[state] = (best[0], best[1], exilus)
        return best[0]

    def moves(self, state: State) -> Iterator[State]:
        chosen, picks = state
        others = [j for j in range(len(self.pool)) if j not in chosen]
        for j in others:
            yield chosen | {j}, picks
        for i in sorted(chosen):
            yield chosen - {i}, picks
        for i in sorted(chosen):
            for j in others:
                yield (chosen - {i}) | {j}, picks
        for slot, options in enumerate(self.choices):
            for k in range(len(options)):
                if k != picks[slot]:
                    yield chosen, (*picks[:slot], k, *picks[slot + 1 :])

    def improve(self) -> None:
        current: State = (frozenset(), tuple(0 for _ in self.choices))
        self.consider(current)
        while True:
            here = self.key(current)
            step = here
            for state in self.moves(current):
                if not self.legal(state[0]):
                    continue
                self.consider(state)
                key = self.key(state)
                if _better(key, step):
                    step = key
            if step is here:
                return
            current = step[2]

    def result(self, status: Literal["optimal", "best_found"]) -> Result:
        assert self.best is not None
        state = self.best[2]
        value, order, exilus = self.cache[state]
        picks = tuple(c[i] for c, i in zip(self.choices, state[1], strict=True))
        return Result(order, exilus, picks, value, status, self.evaluations)

    def _names(self, state: State) -> tuple[str, ...]:
        chosen, picks = state
        mods = sorted(self.pool[i].unique_name for i in chosen)
        options = [
            (o.name if (o := c[i]) is not None else "")
            for c, i in zip(self.choices, picks, strict=True)
        ]
        return (*mods, "|", *options)


def _better(a: Key, b: Key) -> bool:
    """Higher rounded score; ties by the sorted uniqueNames, then the choices (G16)."""
    return a[0] > b[0] or (a[0] == b[0] and a[1] < b[1])
