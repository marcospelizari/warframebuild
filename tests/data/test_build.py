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
