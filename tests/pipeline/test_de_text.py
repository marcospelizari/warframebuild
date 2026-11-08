"""DE markup -> plain text (app/pipeline/sources/de_text.py)."""

import pytest

from app.pipeline.errors import RefreshError
from app.pipeline.sources.de_text import clean_text


def test_clean_text_strips_markup() -> None:
    assert clean_text("+90% <DT_POISON_COLOR>Toxin\r\nx<LINE_SEPARATOR>y") == "+90% Toxin\nx\ny"
    assert clean_text("Remove all. <LOWER_IS_BETTER>7s cooldown.") == "Remove all. 7s cooldown."


def test_damage_tag_without_its_word_keeps_the_type() -> None:
    # Hunter Munitions: the tag is the only place the damage type appears.
    assert clean_text("+30% chance to apply <DT_SLASH_COLOR> on Critical") == (
        "+30% chance to apply Slash on Critical"
    )
    assert clean_text("On <DT_PUNCTURE_COLOR> Puncture: <DT_SENTIENT>Tau") == "On Puncture: Tau"


def test_damage_tag_followed_by_a_de_synonym_is_not_doubled() -> None:
    """Review 2 bug 1: DE writes other words after the tag (Prototype Shock Coils)."""
    assert (
        clean_text("Adds +90% <DT_ELECTRICITY_COLOR>Electric damage") == "Adds +90% Electric damage"
    )
    assert clean_text("<DT_FREEZE_COLOR>Freeze") == "Freeze"
    assert clean_text("+300% <DT_GAS_COLOR>Extra Gas Damage") == "+300% Extra Gas Damage"
    assert clean_text("by a <DT_MAGNETIC>Magnetic Status") == "by a Magnetic Status"  # no _COLOR


def test_unknown_damage_tag_fails() -> None:
    """Review 2 bug 2: a new tag must never vanish from the text silently."""
    with pytest.raises(RefreshError, match="DT_ARCHON_COLOR"):
        clean_text("+30% chance to apply <DT_ARCHON_COLOR> on Critical")
