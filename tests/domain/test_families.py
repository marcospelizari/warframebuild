from app.domain.families import clashes


def test_clashes_by_shared_family() -> None:
    mods = [("split", "F"), ("galvanized", "F"), ("vigilante", None), ("serration", "S")]
    assert clashes(mods) == [("split", "galvanized")]


def test_no_family_never_clashes() -> None:
    assert clashes([("a", None), ("b", None)]) == []
