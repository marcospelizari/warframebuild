import pytest

from app.pipeline.errors import RefreshError
from app.pipeline.sources.wiki_incarnon import clean, genesis, native
from tests.conftest import GENESIS_STUB, LAETUM_STUB


def test_genesis_fills_values_per_variant() -> None:
    perks = {(p.weapon, p.name): p for p in genesis(GENESIS_STUB)}
    assert len(perks) == 4
    prime = perks[("Lex Prime", "Critical Parallel")]
    assert prime.tier == 4
    assert prime.lines == [
        "Increase Base Critical Chance by +19%.",
        "Increase Base Critical Damage Multiplier by +0.4x.",
    ]
    assert perks[("Lex", "Critical Parallel")].lines[0].endswith("+20%.")
    assert perks[("Lex", "Executioner's Dawn")].notes == [
        "The bonus does not apply to the Incarnon form."
    ]


def test_native_page_has_one_weapon() -> None:
    perks = native("Laetum", LAETUM_STUB)
    assert [p.name for p in perks] == ["Devouring Attrition", "Overwhelming Attrition"]
    assert perks[0].notes[0].startswith("Damage bonus is multiplicative")


def test_value_cells_must_cover_every_variant() -> None:
    broken = GENESIS_STUB.replace('| style="text-align:center" | X = 19%\n', "")
    with pytest.raises(RefreshError, match="value cell"):
        genesis(broken)


def test_clean_markup() -> None:
    assert clean("'''+20%''' [[Status Chance|status]] {{D|Heat}} [[File:x.png|64px]]") == (
        "+20% status Heat"
    )
