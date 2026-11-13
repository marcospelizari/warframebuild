import pytest

from app.domain.effects import Support
from app.domain.headshot import Head
from app.gamedata.models import Effects, Mod
from app.gamedata.store import GameData
from app.optimize.loadout import loadout
from app.optimize.scoring import max_score
from app.optimize.search import Option, Result, rounded, search

NONE = Effects(support=Support.FULL, effects=[], unparsed=[])
LEX = (
    "Hornet Strike",
    "Barrel Diffusion",
    "Pistol Gambit",
    "Target Cracker",
    "Heated Charge",
    "Deep Freeze",
    "Pathogen Rounds",
    "Convulsion",
    "Galvanized Shot",
    "Augur Pact",
)


def _run(data: GameData, names: tuple[str, ...], budget: int) -> Result:
    by_name = {m.name: m for m in data.mods.mods}
    lex = next(w for w in data.weapons if w.name == "Lex Prime")
    head = Head(data.reference_head.multiplier, critical=data.reference_head.critical)

    def score(mods: list[Mod], exilus: Mod | None, picks: tuple[Option, ...]) -> float:
        lo = loadout(lex, mods, form="normal", sets=data.set_by_id, exilus=exilus)
        return max_score(lo, head, data.status_rules)

    return search([by_name[n] for n in names], score, budget)


def test_small_pool_is_searched_exhaustively(gamedata: GameData) -> None:
    """10 mods: at most 1,023 sets x 3 element pairings fit the budget."""
    result = _run(gamedata, LEX, 5_000)
    assert result.status == "optimal"
    assert len(result.mods) == 8


def test_heuristic_finds_the_exhaustive_best_on_a_small_pool(gamedata: GameData) -> None:
    best = _run(gamedata, LEX, 5_000)
    found = _run(gamedata, LEX, 3_000)  # below 1,023 x 3: heuristic mode
    assert found.status == "best_found"
    assert rounded(found.score) == rounded(best.score)
    assert {m.name for m in found.mods} == {m.name for m in best.mods}


def test_family_members_never_share_a_build(gamedata: GameData) -> None:
    result = _run(gamedata, ("Target Cracker", "Primed Target Cracker", "Pistol Gambit"), 5_000)
    names = {m.name for m in result.mods}
    assert not {"Target Cracker", "Primed Target Cracker"} <= names


def test_budget_ends_the_search(gamedata: GameData) -> None:
    result = _run(gamedata, LEX, 40)
    assert result.status == "best_found"
    assert result.evaluations == 40


def test_search_is_deterministic(gamedata: GameData) -> None:
    a, b = _run(gamedata, LEX, 3_000), _run(gamedata, LEX, 3_000)
    assert [m.unique_name for m in a.mods] == [m.unique_name for m in b.mods]
    assert a.score == b.score


def test_ninth_mod_goes_to_the_exilus_slot() -> None:
    """Synthetic score: every mod adds 1; only exilus-capable mods may take slot 9."""

    def mod(i: int, exilus: bool) -> Mod:
        return Mod.model_construct(unique_name=f"m{i}", family=None, exilus=exilus, effects=NONE)

    pool = [mod(i, exilus=i == 0) for i in range(10)]
    result = search(pool, lambda mods, ex, picks: len(mods) + (ex is not None), 5_000)
    assert result.status == "optimal"
    assert result.score == 9
    assert result.exilus is not None and result.exilus.unique_name == "m0"


def test_without_exilus_capable_mods_eight_slots(gamedata: GameData) -> None:
    def mod(i: int) -> Mod:
        return Mod.model_construct(unique_name=f"m{i}", family=None, exilus=False, effects=NONE)

    result = search([mod(i) for i in range(10)], lambda mods, ex, picks: float(len(mods)), 5_000)
    assert result.score == pytest.approx(8)
    assert result.exilus is None


def test_choice_slots_are_searched() -> None:
    """Synthetic: two slots, the score adds the option values."""

    class Pick:
        def __init__(self, name: str, value: float) -> None:
            self.name, self.value = name, value

    a, b, c = Pick("a", 1), Pick("b", 3), Pick("c", 2)

    def score(mods: list[Mod], ex: Mod | None, picks: tuple[Option, ...]) -> float:
        return sum(p.value for p in picks if isinstance(p, Pick))

    result = search([], score, 5_000, [[None, a, b], [None, c]])
    assert result.status == "optimal"
    assert result.picks == (b, c)
    heuristic = search([], score, 3, [[None, a, b], [None, c]])
    assert heuristic.status == "best_found"


def test_starts_reach_a_pair_that_one_mod_moves_cannot() -> None:
    """The primer's Viral needs Toxin and Cold together: either alone scores less than the
    plain build, so the climb from empty never adds them (G49)."""
    mods = [
        Mod.model_construct(unique_name=n, name=n, family=None, exilus=False, effects=NONE)
        for n in ("toxin", "cold", "status")
    ]

    def score(regular: list[Mod], exilus: Mod | None, picks: tuple[Option, ...]) -> float:
        names = {m.name for m in regular}
        pair = {"toxin", "cold"} <= names
        return (5.0 if pair else -1.0 * len(names & {"toxin", "cold"})) + ("status" in names)

    plain = search(mods, score, budget=20)  # under the exhaustive size (24): a local climb
    assert plain.status == "best_found" and {m.name for m in plain.mods} == {"status"}
    seeded = search(mods, score, budget=20, starts=[mods[:2]])
    assert {m.name for m in seeded.mods} == {"toxin", "cold", "status"}
