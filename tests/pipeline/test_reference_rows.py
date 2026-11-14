import json

import pytest

from app.pipeline import reference_rows
from app.pipeline.changes import EntryDiff
from app.pipeline.refresh import Paths


def test_reference_rows_and_staleness_by_date(paths: Paths) -> None:
    rows = reference_rows.reference_rows(paths.reference)
    keys = {(r.file, r.key) for r in rows}
    epitaph = "/Lotus/Weapons/Tenno/Pistols/TnWraitheSidearm/TnWraitheSidearmWeapon"
    assert ("fire_overrides.json", epitaph) in keys
    assert ("fire_overrides.json", "beam_ramp_start") in keys
    assert ("mod_filter.json", "expert") in keys
    assert reference_rows.stale_rows(rows, "2026-11-08") == []
    assert len(reference_rows.stale_rows(rows, "2026-12-01")) == len(rows)


def test_verified_must_be_a_date(paths: Paths) -> None:
    rules = json.loads((paths.reference / "mod_filter.json").read_text())
    rules["rules"][0]["verified"] = "Update 44.0"
    (paths.reference / "mod_filter.json").write_text(json.dumps(rules))
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        reference_rows.reference_rows(paths.reference)


def test_family_correction_listed_when_a_member_changes(paths: Paths) -> None:
    """Review R16: correction rows are keyed by their own id; their `mods` count."""
    rows = reference_rows.reference_rows(paths.reference)
    join = next(r for r in rows if r.key == "galvanized-aptitude-rifle-aptitude")
    diff = EntryDiff(ids={join.depends_on[0]})
    assert join in reference_rows.touched_rows(rows, diff)


def test_single_reference_row_is_listed(paths: Paths) -> None:
    rows = reference_rows.reference_rows(paths.reference)
    assert ("headshot.json", "Grineer humanoid head") in {(r.file, r.label) for r in rows}
