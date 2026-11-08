import math

import pytest

from app.domain.damage import composition, quantize, scaled
from app.domain.effects import DamageType as D
from app.domain.elements import Part


def test_quantization_example() -> None:
    """Saved Damage/Calculation, Quantization: 30/30/40 -> 31.25/31.25/40.625 (103.125)."""
    out = composition({D.IMPACT: 30, D.PUNCTURE: 30, D.SLASH: 40}, [], {})
    assert out == {D.IMPACT: 31.25, D.PUNCTURE: 31.25, D.SLASH: 40.625}
    assert math.fsum(out.values()) == 103.125


def test_physical_mod_example() -> None:
    """Same page: Maim (+120% Slash) on the 40 Slash -> 87.5."""
    out = composition({D.IMPACT: 30, D.PUNCTURE: 30, D.SLASH: 40}, [], {D.SLASH: 1.2})
    assert out[D.SLASH] == 87.5


def test_nagantaka_prime_full_example() -> None:
    """Same page: Cryo Rounds, Malignant Force, Hellfire, Piercing Caliber, Gas Valence
    Formation in that order -> 951.5 total."""
    base = {D.IMPACT: 1.73, D.PUNCTURE: 15.57, D.SLASH: 155.7}
    mods = [Part(D.COLD, 0.9), Part(D.TOXIN, 0.6), Part(D.HEAT, 0.9), Part(D.GAS, 2.0)]
    out = composition(base, mods, {D.PUNCTURE: 1.2})
    assert out == {
        D.PUNCTURE: 32.4375,
        D.SLASH: 156.78125,
        D.VIRAL: 259.5,
        D.HEAT: 156.78125,
        D.GAS: 346.0,
    }  # Impact quantizes to 0 and is dropped
    assert math.fsum(out.values()) == 951.5


def test_damage_bonus_scales_quantized_values() -> None:
    """Same page: Serration multiplies numerator and scale alike, so it scales the total."""
    out = composition({D.IMPACT: 30, D.PUNCTURE: 30, D.SLASH: 40}, [], {})
    assert math.fsum(scaled(out, 1 + 1.65).values()) == pytest.approx(103.125 * 2.65)


def test_quantize_rounds_half_away_from_zero() -> None:
    assert quantize(1.5, 32) == 2
    assert quantize(-1.5, 32) == -2
    assert quantize(1.49, 32) == 1


def test_physical_bonus_on_a_non_physical_type_fails() -> None:
    with pytest.raises(ValueError, match="non-physical"):
        composition({D.IMPACT: 10}, [], {D.HEAT: 1.0})
