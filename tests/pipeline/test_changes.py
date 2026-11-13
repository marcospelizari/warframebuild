import json
from pathlib import Path

from app.domain.effects import Support
from app.gamedata.changes import SNAPSHOT, Change, Changes, Kind, Shown, Snapshot, read_changes
from app.pipeline import changes, reference_rows
from app.pipeline.refresh import Paths, run

HORNET = "/Lotus/Upgrades/Mods/Pistol/WeaponDamageAmountMod"
PH_LINE = "[PH] +1 max Puncture stacks"


def _edit_de(paths: Paths, file: str, key: str, name: str, edit: object) -> None:
    path = paths.raw / "de" / file
    data = json.loads(path.read_text())
    entry = next(e for e in data[key] if e.get("uniqueName") == name or e["name"] == name)
    edit(entry)  # type: ignore[operator]
    path.write_text(json.dumps(data))


def _raise_lex_crit(paths: Paths) -> None:
    def edit(e: dict[str, float]) -> None:
        e["criticalChance"] += 0.05

    _edit_de(paths, "ExportWeapons_en.json", "ExportWeapons", "Lex Prime", edit)


def _add_ph_line_to_hornet(paths: Paths) -> None:
    def edit(e: dict[str, list[dict[str, list[str]]]]) -> None:
        e["levelStats"][-1]["stats"] = ["+240% Damage", PH_LINE]

    _edit_de(paths, "ExportUpgrades_en.json", "ExportUpgrades", HORNET, edit)


def test_gun_change_lists_fields_and_touched_rows(paths: Paths) -> None:
    run(paths, offline=True, fetch_images=False)
    _raise_lex_crit(paths)
    fire = json.loads((paths.reference / "fire_overrides.json").read_text())
    lex = next(
        e
        for e in json.loads((paths.raw / "wfcd/Secondary.json").read_text())
        if e["name"] == "Lex Prime"
    )
    fire["weapons"][lex["uniqueName"]] = {"name": "Lex Prime", "verified": "2026-10-01"}
    (paths.reference / "fire_overrides.json").write_text(json.dumps(fire))

    report = run(paths, offline=True, fetch_images=False)
    assert report.diff.changed["weapons"] == ["Lex Prime"]
    assert sorted((r.file, r.label) for r in report.touched) == [
        ("fire_overrides.json", "Lex Prime"),
        ("headshot.json", "Lex Prime"),  # headshot row
        ("headshot.json", "Lex Prime"),  # flat_heads row
        ("main_attack.json", "Lex Prime"),
    ]
    found = read_changes(paths.gamedata)
    assert found is not None and found.sources_changed
    (entry,) = found.entries
    assert [x for x in entry.before if x.startswith("critical_chance")] != [
        x for x in entry.after if x.startswith("critical_chance")
    ]


def test_mod_text_change_shows_old_and_new_with_support_drop_first(paths: Paths) -> None:
    """The Bore case: a new stat line the parser cannot model drops support (U1)."""
    run(paths, offline=True, fetch_images=False)
    _raise_lex_crit(paths)
    _add_ph_line_to_hornet(paths)
    report = run(paths, offline=True, fetch_images=False)

    found = read_changes(paths.gamedata)
    assert found is not None
    first = found.entries[0]
    assert (first.name, first.kind, first.change) == ("Hornet Strike", Kind.MOD, Change.CHANGED)
    assert first.support_dropped and first.support_after != Support.FULL
    assert first.before[0] == "+220% Damage" and first.after[:2] == ["+240% Damage", PH_LINE]
    assert PH_LINE in first.unparsed

    text = "\n".join(report.lines())
    assert "support dropped (1)" in text and "Hornet Strike (mod): full ->" in text
    md_path = (
        paths.raw.parent / f"patch-report-{report.meta.changed_on}-{report.meta.dataset_hash}.md"
    )
    assert f"full patch report: {md_path}" in text
    md = md_path.read_text()
    assert "- +220% Damage" in md and f"+ {PH_LINE}" in md
    assert md.index("Hornet Strike") < md.index("Lex Prime")


def test_comparison_survives_a_schema_change(paths: Paths) -> None:
    """The snapshot has its own format: a gamedata schema bump keeps the diff."""
    run(paths, offline=True, fetch_images=False)
    meta_path = paths.gamedata / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta["schema_version"] = 1
    meta_path.write_text(json.dumps(meta))
    _raise_lex_crit(paths)
    report = run(paths, offline=True, fetch_images=False)
    assert report.diff.unavailable is None
    assert report.diff.changed["weapons"] == ["Lex Prime"]


def test_rerun_on_same_data_keeps_the_record_and_writes_no_report(paths: Paths) -> None:
    run(paths, offline=True, fetch_images=False)
    _raise_lex_crit(paths)
    first = run(paths, offline=True, fetch_images=False)
    report_path = (
        paths.raw.parent / f"patch-report-{first.meta.changed_on}-{first.meta.dataset_hash}.md"
    )
    report_path.unlink()
    again = run(paths, offline=True, fetch_images=False)
    assert again.diff.changed["weapons"] == ["Lex Prime"]  # how this dataset arrived
    assert not report_path.exists()


def test_dataset_without_snapshot_is_reported_unavailable(paths: Paths) -> None:
    run(paths, offline=True, fetch_images=False)
    (paths.gamedata / SNAPSHOT).unlink()
    _raise_lex_crit(paths)
    report = run(paths, offline=True, fetch_images=False)
    assert report.diff.unavailable and "no snapshot.json" in report.diff.unavailable
    assert len(report.touched) == len(reference_rows.reference_rows(paths.reference))
    md = Path(
        paths.raw.parent / f"patch-report-{report.meta.changed_on}-{report.meta.dataset_hash}.md"
    ).read_text()
    assert "No comparison: no snapshot.json" in md


def test_perk_change_touches_its_gun() -> None:
    def perk(lines: list[str]) -> Snapshot:
        shown = Shown(
            kind=Kind.PERK, name="Laetum: X", lines=lines, support=Support.FULL, unparsed=[]
        )
        return Snapshot(entries={"/Gun#X": shown})

    diff = changes.entry_diff(
        Changes(
            from_hash="a",
            to_hash="b",
            sources_changed=True,
            entries=changes.compare(perk(["+10%"]), perk(["+20%"])),
        )
    )
    assert diff.changed["perks"] == ["Laetum: X"]
    assert diff.ids == {"/Gun#X", "/Gun"}


def test_mod_field_change_without_text_change_is_listed(paths: Paths) -> None:
    """Review: drain or polarity changes count too (exilus/family rows read the mod)."""
    run(paths, offline=True, fetch_images=False)

    def edit(e: dict[str, int]) -> None:
        e["baseDrain"] = 6

    _edit_de(paths, "ExportUpgrades_en.json", "ExportUpgrades", HORNET, edit)
    report = run(paths, offline=True, fetch_images=False)
    assert report.diff.changed["mods"] == ["Hornet Strike"]
    assert HORNET in report.diff.ids


def test_source_key_order_is_not_a_change() -> None:
    assert changes._flat({"b": 1, "a": {"y": 2, "x": 3}}, "") == changes._flat(
        {"a": {"x": 3, "y": 2}, "b": 1}, ""
    )


def test_switched_off_override_is_listed_first(paths: Paths) -> None:
    """G90 U2: a changed text switches the override off; the update still goes out."""
    run(paths, offline=True, fetch_images=False)
    path = paths.reference / "overrides.json"
    data = json.loads(path.read_text())
    key = next(k for k in data["entries"] if k.endswith("#Devouring Attrition"))
    data["entries"][key]["text"] = ["50% chance to deal +1500% damage on non-critical hits"]
    path.write_text(json.dumps(data))

    report = run(paths, offline=True, fetch_images=False)
    lines = report.lines()
    assert f"  {key}" in lines
    assert lines.index("overrides switched off (1): their text changed, rewrite them:") < next(
        i for i, line in enumerate(lines) if line.startswith("full patch report")
    )
    md = (
        paths.raw.parent / f"patch-report-{report.meta.changed_on}-{report.meta.dataset_hash}.md"
    ).read_text()
    assert f"## Override switched off: {key}" in md
    assert "- 50% chance to deal +1500% damage on non-critical hits" in md
