import json

import pytest

from app.data.build import RefreshError, build, clean_text
from app.data.refresh import Paths


def test_weapons_join_and_exclusions(paths: Paths) -> None:
    data = build(paths.raw, paths.reference)
    names = {w.name for w in data.weapons}
    assert "Braton Prime" in names
    assert {e.name: e.reason for e in data.excluded_weapons}.keys() == {"Lanka", "Sirocco"}
    assert {j.unique_name for j in data.joins} == {w.unique_name for w in data.weapons}


def test_damage_slots(paths: Paths) -> None:
    weapons = {w.name: w for w in build(paths.raw, paths.reference).weapons}
    assert weapons["Braton Prime"].damage == {"impact": 1.75, "puncture": 12.25, "slash": 21.0}
    assert "gas" in weapons["Cyanex"].damage
    assert "tau" in weapons["Haalvu"].damage


def test_attack_chances_are_fractions(paths: Paths) -> None:
    braton = next(w for w in build(paths.raw, paths.reference).weapons if w.name == "Braton Prime")
    normal = braton.attacks[0]
    assert normal.critical_chance == pytest.approx(braton.critical_chance)
    assert braton.attacks[2].falloff is not None


def test_slug_collision_is_disambiguated(paths: Paths) -> None:
    slugs = [w.slug for w in build(paths.raw, paths.reference).weapons if w.name == "Grimoire"]
    assert len(slugs) == 2 and len(set(slugs)) == 2


def test_mod_filter(paths: Paths) -> None:
    data = build(paths.raw, paths.reference)
    by_name = {m.name: m for m in data.mods}
    assert by_name["Serration"].unique_name == "/Lotus/Upgrades/Mods/Rifle/WeaponDamageAmountMod"
    assert "/Expert/" not in by_name["Split Chamber"].unique_name
    assert "/Expert/" in by_name["Primed Cryo Rounds"].unique_name
    assert "Rifle Riven Mod" not in by_name
    assert set(data.denied_mods) >= {"beginner", "intermediate", "expert", "no-level-stats"}
    assert data.mod_sets  # Vigilante set kept for its member


def test_unclassified_duplicate_name_fails(paths: Paths) -> None:
    rules_path = paths.reference / "mod_filter.json"
    rules = json.loads(rules_path.read_text())
    rules["rules"] = [r for r in rules["rules"] if r["id"] != "beginner"]
    rules_path.write_text(json.dumps(rules))
    with pytest.raises(RefreshError, match="Serration"):
        build(paths.raw, paths.reference)


def test_gun_without_fire_rate_fails(paths: Paths) -> None:
    (paths.reference / "fire_overrides.json").write_text('{"weapons": {}}')
    with pytest.raises(RefreshError, match="Lanka"):
        build(paths.raw, paths.reference)


def test_clean_text_strips_markup() -> None:
    assert clean_text("+90% <DT_POISON_COLOR>Toxin\r\nx<LINE_SEPARATOR>y") == "+90% Toxin\nx\ny"


def test_fire_rate_error_names_the_field_that_works(paths: Paths) -> None:
    """Review bug 5: the advice must point at what the build reads (`exclude`)."""
    (paths.reference / "fire_overrides.json").write_text('{"weapons": {}}')
    with pytest.raises(RefreshError, match="`exclude` entry"):
        build(paths.raw, paths.reference)


@pytest.mark.parametrize(
    "field,value",
    [("criticalChance", float("nan")), ("procChance", -0.1), ("fireRate", float("inf"))],
)
def test_rejects_non_finite_or_negative_numbers(paths: Paths, field: str, value: float) -> None:
    weapons_path = paths.raw / "de/ExportWeapons_en.json"
    data = json.loads(weapons_path.read_text())
    braton = next(w for w in data["ExportWeapons"] if w["name"] == "Braton Prime")
    braton[field] = value
    weapons_path.write_text(json.dumps(data))
    with pytest.raises(RefreshError, match="Braton Prime"):
        build(paths.raw, paths.reference)


def test_status_chance_above_one_is_allowed(paths: Paths) -> None:
    weapons_path = paths.raw / "de/ExportWeapons_en.json"
    data = json.loads(weapons_path.read_text())
    next(w for w in data["ExportWeapons"] if w["name"] == "Braton Prime")["procChance"] = 1.5
    weapons_path.write_text(json.dumps(data))
    braton = next(w for w in build(paths.raw, paths.reference).weapons if w.name == "Braton Prime")
    assert braton.status_chance == 1.5


def test_wfcd_speed_zero_means_no_own_fire_rate() -> None:
    from app.data.build.weapons import _attack

    dot = {
        "name": "Corrosive DoT",
        "speed": 0,
        "crit_chance": 0,
        "crit_mult": 1,
        "status_chance": 0,
        "damage": {"corrosive": 10},
    }
    assert _attack(dot, "Tysis").fire_rate is None
