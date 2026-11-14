import pytest

from app.optimize.tiers import tier

CASES = [(1.0, "S"), (2.0, "S"), (2.01, "A"), (8.0, "B"), (9, "C"), (32, "D"), (64, "E"), (65, "F")]


@pytest.mark.parametrize(("ratio", "expected"), CASES)
def test_each_tier_doubles_the_ratio_to_the_fastest_gun(ratio: float, expected: str) -> None:
    assert tier(ratio) == expected
