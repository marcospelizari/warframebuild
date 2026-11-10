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
        flat = table["flat_heads"].get(w.unique_name, {}).get("forms", [])
        assert [h.form for h in w.headshot if h.flat] == flat, w.name
        separate = w.unique_name in table["separate_extra"]
        assert all(h.separate_extra == separate for h in w.headshot), w.name
    assert set(table["weapons"]) <= {w.unique_name for w in data.weapons}


def test_zoom_and_extra_headshot_from_the_module(paths: Paths) -> None:
    weapons = {w.name: w for w in build(paths.raw, paths.reference).weapons}
    lanka = weapons["Lanka"].zoom
    assert lanka is not None and lanka.effects[0].operation == "add"  # overrides.json #zoom
    assert lanka.effects[0].value == 0.5  # highest zoom (8x)
    perfect = next(a for a in weapons["Nataruk"].attacks if a.name == "Perfect Shot")
    assert perfect.extra_headshot == -2
    assert weapons["Braton Prime"].zoom is None


def test_flat_head_and_reference_head(paths: Paths) -> None:
    data = build(paths.raw, paths.reference)
    lex = next(w for w in data.weapons if w.name == "Lex Prime")
    assert [(h.form, h.flat) for h in lex.headshot] == [("normal", False), ("incarnon", True)]
    assert (data.reference_head.multiplier, data.reference_head.critical) == (3.0, True)


def test_flat_head_on_a_body_form_fails(paths: Paths) -> None:
    def change(d: dict[str, Any]) -> None:
        d["weapons"][LEX_PRIME]["forms"] = ["normal"]

    _edit(paths, change)
    with pytest.raises(RefreshError, match="flat head on a body form"):
        build(paths.raw, paths.reference)


def test_reference_head_is_required(paths: Paths) -> None:
    _edit(paths, lambda d: d.pop("reference_head"))
    with pytest.raises(RefreshError, match="reference_head"):
        build(paths.raw, paths.reference)


def test_row_without_name_inside_a_class_fails_cleanly(paths: Paths) -> None:
    vectis = next(w for w in build(paths.raw, paths.reference).weapons if w.name == "Vectis")
    row = {
        "forms": ["normal"],
        "reason": "r",
        "source": "project decision",
        "verified": "2026-11-09",
    }
    _edit(paths, lambda d: d["weapons"].update({vectis.unique_name: row}))
    with pytest.raises(RefreshError, match="covered by class"):
        build(paths.raw, paths.reference)


def test_separate_extra_needs_a_positive_module_value(paths: Paths) -> None:
    row = {"name": "Lanka", "reason": "r", "source": "project decision", "verified": "2026-11-09"}
    lanka = next(w for w in build(paths.raw, paths.reference).weapons if w.name == "Lanka")
    _edit(paths, lambda d: d.setdefault("separate_extra", {}).update({lanka.unique_name: row}))
    with pytest.raises(RefreshError, match="separate_extra"):
        build(paths.raw, paths.reference)


def test_committed_beam_ramp_per_attack() -> None:
    """An attack's own module Trigger decides the beam ramp (Continuous_Weapon:47-71)."""
    weapons = {w.name: w for w in store.load(ROOT / "gamedata").weapons}
    ramp = {n: {a.name: a.beam_ramp_start for a in weapons[n].attacks} for n in weapons}
    assert ramp["Torid"]["Incarnon Form"] == 0.2 and ramp["Torid"]["Grenade Impact"] is None
    assert ramp["Atomos"]["Normal Attack"] == 0.2 and ramp["Atomos"]["Incarnon Form"] is None
