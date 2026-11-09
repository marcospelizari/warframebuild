import pytest

from app.domain.effects import DamageType
from app.pipeline.errors import RefreshError
from app.pipeline.sources.wiki_progenitor import parse

PAGE = """== Kuva Weapons Checklist ==
=== Obtained ===
{{Checklist|
*{{Weapon|Kuva Brakk}}
*{{Weapon|Kuva Hek}}
}}
=== Max Fusioned (+60% damage) ===
{{Checklist|
*{{Weapon|Kuva Shildeg}}
}}
===Elemental Bonus===

Bonus damage of one damage type which can either be {{D|Impact}}, {{D|Heat}} or
{{D|Radiation}}, ranging from 25-60% of the weapon's '''base damage'''.

===[[Valence Fusion]]===
"""


def test_parses_guns_elements_and_max_share() -> None:
    p = parse("Kuva_Weapons", PAGE)
    assert p.guns == {"Kuva Brakk", "Kuva Hek"}
    assert p.elements == (DamageType.IMPACT, DamageType.HEAT, DamageType.RADIATION)
    assert p.max_share == 0.6


@pytest.mark.parametrize(
    ("old", "new"),
    [("=== Obtained ===", "=== Owned ==="), ("{{D|Heat}}", "{{D|Fire}}"), ("25-60%", "")],
)
def test_changed_page_fails(old: str, new: str) -> None:
    with pytest.raises(RefreshError):
        parse("Kuva_Weapons", PAGE.replace(old, new))
