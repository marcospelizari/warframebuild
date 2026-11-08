from app.domain.effects import DamageType as D
from app.domain.elements import Part, combine


def kinds(out: dict[D, list[Part]]) -> set[D]:
    return set(out)


def test_amprex_innate_electricity_comes_last() -> None:
    """Saved Damage: Hellfire + Cryo Rounds on an Amprex -> Blast + its own Electricity."""
    innate = [Part(D.ELECTRICITY, innate=22)]
    assert kinds(combine([Part(D.HEAT, 0.9), Part(D.COLD, 0.9)], innate)) == {
        D.BLAST,
        D.ELECTRICITY,
    }
    # Hellfire alone combines with the innate Electricity.
    assert kinds(combine([Part(D.HEAT, 0.9)], innate)) == {D.RADIATION}


def test_mod_of_the_innate_element_moves_it_first() -> None:
    """Saved Damage: Stormbringer top left moves Amprex's Electricity to the front."""
    innate = [Part(D.ELECTRICITY, innate=22)]
    out = combine([Part(D.ELECTRICITY, 0.9), Part(D.HEAT, 0.9), Part(D.COLD, 0.9)], innate)
    assert kinds(out) == {D.RADIATION, D.COLD}
    assert Part(D.ELECTRICITY, innate=22) in out[D.RADIATION]


def test_first_mod_of_an_element_sets_its_place() -> None:
    """Saved Calculating_Bonuses: Hellfire, Cryo Rounds and Thermite Rounds on an Amprex
    -> Blast and Electricity, whatever the order of the two Heat mods."""
    innate = [Part(D.ELECTRICITY, innate=22)]
    mods = [Part(D.HEAT, 0.9), Part(D.COLD, 0.9), Part(D.HEAT, 0.6)]
    out = combine(mods, innate)
    assert kinds(out) == {D.BLAST, D.ELECTRICITY}
    assert sum(p.mod_fraction for p in out[D.BLAST]) == 0.9 + 0.9 + 0.6


def test_two_innate_primaries_in_hcet_order() -> None:
    """Saved Damage: with two innate primaries the one first in Heat > Cold > Electricity >
    Toxin is second to last; a single mod element combines with it."""
    innate = [Part(D.TOXIN, innate=10), Part(D.COLD, innate=10)]
    assert kinds(combine([Part(D.HEAT, 0.9)], innate)) == {D.BLAST, D.TOXIN}


def test_secondary_elements_never_combine() -> None:
    innate = [Part(D.BLAST, innate=100)]  # Ogris
    out = combine([Part(D.HEAT, 0.9), Part(D.COLD, 0.9)], innate)
    assert kinds(out) == {D.BLAST}
    assert len(out[D.BLAST]) == 3
