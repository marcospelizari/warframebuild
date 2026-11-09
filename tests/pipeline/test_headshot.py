import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.gamedata import store
from app.pipeline.build import build
from app.pipeline.errors import RefreshError
from app.pipeline.refresh import Paths

ROOT = Path(__file__).resolve().parents[2]
LEX_PRIME = "/Lotus/Weapons/Tenno/Pistols/PrimeLex/PrimeLex"
BRATON_PRIME = "/Lotus/Weapons/Tenno/Rifle/BratonPrime"


def _forms(paths: Paths) -> dict[str, list[str]]:
    return {w.name: [h.form for h in w.headshot] for w in build(paths.raw, paths.reference).weapons}


def test_classes_and_rows_mark_forms(paths: Paths) -> None:
    forms = _forms(paths)
    assert forms["Lanka"] == ["normal"]  # Sniper class
    assert forms["Nataruk"] == ["normal"]  # Bow class
    assert forms["Lex Prime"] == ["normal", "incarnon"]  # weapon row
    assert forms["Braton Prime"] == []


def test_source_page_becomes_its_title(paths: Paths) -> None:
    lex = next(w for w in build(paths.raw, paths.reference).weapons if w.name == "Lex Prime")
    assert lex.headshot[0].source == "Incarnon_Evolutions"
    assert "Executioner's Dawn" in lex.headshot[0].reason
    lanka = next(w for w in build(paths.raw, paths.reference).weapons if w.name == "Lanka")
    assert lanka.headshot[0].source is None  # project decision


def _edit(paths: Paths, change: Callable[[dict[str, Any]], None]) -> None:
    table = paths.reference / "headshot.json"
    data = json.loads(table.read_text())
    change(data)
    table.write_text(json.dumps(data))


def _row(name: str, forms: list[str], source: str = "project decision") -> dict[str, Any]:
    return {"name": name, "forms": forms, "reason": "r", "source": source, "verified": "2026-11-09"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["weapons"].update({"/Nope": _row("Nope", ["normal"])}), "unknown"),
        (lambda d: d["classes"].update({"Archgun": d["classes"]["Bow"]}), "unknown classes"),
        (
            lambda d: d["weapons"].update({BRATON_PRIME: _row("Braton Prime", ["incarnon"])}),
            "subset",
        ),
        (lambda d: d["weapons"].update({BRATON_PRIME: _row("Braton", ["normal"])}), "name"),
        (
            lambda d: d["weapons"].update({BRATON_PRIME: _row("Braton Prime", ["normal"], "X")}),
            "saved page",
        ),
        (lambda d: d["weapons"][LEX_PRIME].pop("verified"), "verified"),
        (lambda d: d["weapons"][LEX_PRIME].update({"forms": []}), "subset"),
        (lambda d: d["classes"]["Bow"].update({"forms": ["normal"]}), "unknown keys"),
    ],
)
def test_invalid_rows_fail(
    paths: Paths, change: Callable[[dict[str, Any]], None], message: str
) -> None:
    _edit(paths, change)
    with pytest.raises(RefreshError, match=message):
        build(paths.raw, paths.reference)


def test_row_inside_a_class_fails(paths: Paths) -> None:
    vectis = next(w for w in build(paths.raw, paths.reference).weapons if w.name == "Vectis")
    _edit(paths, lambda d: d["weapons"].update({vectis.unique_name: _row("Vectis", ["normal"])}))
    with pytest.raises(RefreshError, match="covered by class"):
        build(paths.raw, paths.reference)


def test_committed_rows_match_gamedata() -> None:
    """The fixtures hold a few guns: every row is checked against the committed gamedata/."""
    data = store.load(ROOT / "gamedata")
    table = json.loads((ROOT / "reference/headshot.json").read_text())
    incarnon = {i.unique_name for i in data.incarnon}
    for w in data.weapons:
        row = table["weapons"].get(w.unique_name)
        if row:
            expected = row["forms"]
        elif w.weapon_type in table["classes"]:
            expected = ["normal", "incarnon"] if w.unique_name in incarnon else ["normal"]
        else:
            expected = []
        assert [h.form for h in w.headshot] == expected, w.name
    assert set(table["weapons"]) <= {w.unique_name for w in data.weapons}
