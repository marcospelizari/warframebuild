"""G90 U7/U8: a new gun or arcane with incomplete data is excluded with a reason; one the
previous dataset had still fails the refresh."""

import json

import pytest

from app.gamedata.models import Exclusion
from app.pipeline.build import Dataset, build
from app.pipeline.build.gaps import Established
from app.pipeline.errors import RefreshError
from app.pipeline.refresh import Paths, Report, run

BRATON = "/Lotus/Weapons/Tenno/Rifle/BratonPrime"


def _established(paths: Paths, *, without: set[str]) -> Established:
    """The fixture dataset as the previous one, minus the `without` names."""
    data = build(paths.raw, paths.reference)
    return Established(
        {w.unique_name for w in data.weapons if w.name not in without},
        {a.unique_name for a in data.arcanes if a.name not in without},
    )


def _reasons(data: Dataset) -> dict[str, str]:
    return {e.name: e.reason for e in data.excluded_weapons}


def _drop_wfcd_gun(paths: Paths, uid: str) -> None:
    path = paths.raw / "wfcd/Primary.json"
    path.write_text(json.dumps([w for w in json.loads(path.read_text()) if w["uniqueName"] != uid]))


def test_new_gun_wfcd_lacks_is_excluded(paths: Paths) -> None:
    """U8: DE has it, WFCD does not yet; its reference rows wait for it."""
    established = _established(paths, without={"Braton Prime"})
    _drop_wfcd_gun(paths, BRATON)
    data = build(paths.raw, paths.reference, established)
    assert _reasons(data)["Braton Prime"] == "in the game files, not in WFCD's data yet"
    assert BRATON not in {w.unique_name for w in data.weapons}
    assert BRATON not in {j.unique_name for j in data.joins}
    pending = {e.name: e.pending for e in data.excluded_weapons}
    assert pending == {"Braton Prime": True, "Sirocco": False, "Grimoire": False}  # hand ones stay


def test_known_gun_wfcd_lost_still_fails(paths: Paths) -> None:
    established = _established(paths, without=set())
    _drop_wfcd_gun(paths, BRATON)
    with pytest.raises(RefreshError, match="Braton Prime: in the game files, not in WFCD"):
        build(paths.raw, paths.reference, established)


def test_new_gun_without_fire_rate_or_magazine_is_excluded(paths: Paths) -> None:
    """U7: Lanka's module loses its no-delay rule (DE rate 0), Convectrix its magazine."""
    established = _established(paths, without={"Lanka", "Convectrix"})
    module = paths.raw / "wiki/Module_Weapons_data_primary.lua"
    text = module.read_text().replace("FireRate = math.huge", "FireRate = 1")
    module.write_text(text.replace("\t\tMagazine = 70,\n", ""))
    reasons = _reasons(build(paths.raw, paths.reference, established))
    assert reasons["Lanka"].startswith("no usable fire rate")
    assert reasons["Convectrix"].startswith("no magazine size")


def test_new_incarnon_gun_without_main_attack_row_is_excluded(paths: Paths) -> None:
    """U7: perks but no reference/main_attack.json row; its perk overrides wait unused."""
    established = _established(paths, without={"Lex Prime"})
    table = paths.reference / "main_attack.json"
    rows = json.loads(table.read_text())
    rows["weapons"] = {u: r for u, r in rows["weapons"].items() if r["name"] != "Lex Prime"}
    table.write_text(json.dumps(rows))
    data = build(paths.raw, paths.reference, established)
    assert "no row in reference/main_attack.json" in _reasons(data)["Lex Prime"]
    assert "Lex Prime" not in {w.name for w in data.weapons}
    assert "Lex Prime" not in {i.name for i in data.incarnon}


def test_new_arcane_wfcd_lacks_is_left_out(paths: Paths) -> None:
    """U8: DE has it, WFCD has not typed its slot yet."""
    established = _established(paths, without={"Primary Merciless"})
    path = paths.raw / "wfcd/Arcanes.json"
    arcanes = json.loads(path.read_text())
    path.write_text(json.dumps([a for a in arcanes if a["name"] != "Primary Merciless"]))
    data = build(paths.raw, paths.reference, established)
    assert [e.name for e in data.excluded_arcanes] == ["Primary Merciless"]
    assert "Primary Merciless" not in {a.name for a in data.arcanes}


def test_left_out_arcane_is_listed_for_you(paths: Paths) -> None:
    meta = run(paths, offline=True, fetch_images=False).meta
    gap = Exclusion(unique_name="/A", name="Primary New", reason="in the game files, not in WFCD")
    report = Report(meta=meta, previous=meta, excluded_arcanes=[gap])
    assert "Primary New (arcane) left out: in the game files, not in WFCD" in report.needs_you()
