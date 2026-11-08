import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.effects import DamageType, Stat, Support, Trigger
from app.gamedata.models import Category, Weapon
from app.pipeline.build import build
from app.pipeline.errors import RefreshError
from app.pipeline.refresh import Paths


def test_weapons_join_and_exclusions(paths: Paths) -> None:
    data = build(paths.raw, paths.reference)
    names = {w.name for w in data.weapons}
    assert "Braton Prime" in names
    assert {e.name: e.reason for e in data.excluded_weapons}.keys() == {"Sirocco"}
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
    assert "Comet Rounds" not in by_name
    assert set(data.denied_mods) >= {
        "beginner",
        "intermediate",
        "expert",
        "conclave",
        "no-level-stats",
    }
    assert data.mod_sets  # Vigilante set kept for its member


def test_unclassified_duplicate_name_fails(paths: Paths) -> None:
    rules_path = paths.reference / "mod_filter.json"
    rules = json.loads(rules_path.read_text())
    rules["rules"] = [r for r in rules["rules"] if r["id"] != "intermediate"]
    rules_path.write_text(json.dumps(rules))
    with pytest.raises(RefreshError, match="Serration"):
        build(paths.raw, paths.reference)


def test_kept_starter_copy_fails(paths: Paths) -> None:
    """export-plus isStarter marks exactly the /Beginner/ copies: a gap in the rule fails."""
    rules_path = paths.reference / "mod_filter.json"
    rules = json.loads(rules_path.read_text())
    rules["rules"] = [r for r in rules["rules"] if r["id"] != "beginner"]
    rules_path.write_text(json.dumps(rules))
    with pytest.raises(RefreshError, match=r"isStarter.*WeaponDamageAmountModBeginner"):
        build(paths.raw, paths.reference)


def test_export_plus_tags_are_stored(paths: Paths) -> None:
    data = build(paths.raw, paths.reference)
    weapons = {w.name: w for w in data.weapons}
    mods = {m.name: m for m in data.mods}
    assert weapons["Braton Prime"].compatibility_tags == ["ASSAULT_AMMO"]
    assert mods["Sniper Ammo Mutation"].compatibility_tags == ["LAUNCHER_AMMO", "SNIPER_AMMO"]
    assert mods["Semi-Rifle Cannonade"].compatibility_tags == ["SEMI_AUTO"]
    assert mods["Semi-Rifle Cannonade"].incompatibility_tags == ["MODULAR_GUN"]
    assert mods["Serration"].compatibility_tags == []
    assert mods["Serration"].incompatibility_tags == []


def test_entry_missing_in_export_plus_has_unknown_tags(paths: Paths) -> None:
    """export-plus can lag DE after an update: the entry is kept, its tags are None."""
    for name, uid in (
        ("ExportWeapons.json", "/Lotus/Weapons/Tenno/Rifle/BratonPrime"),
        ("ExportUpgrades.json", "/Lotus/Upgrades/Mods/Rifle/WeaponDamageAmountMod"),
    ):
        path = paths.raw / "export-plus" / name
        data = json.loads(path.read_text())
        del data[uid]
        path.write_text(json.dumps(data))
    data = build(paths.raw, paths.reference)
    assert next(w for w in data.weapons if w.name == "Braton Prime").compatibility_tags is None
    serration = next(m for m in data.mods if m.name == "Serration")
    assert serration.compatibility_tags is None and serration.incompatibility_tags is None


def test_export_plus_tags_must_be_strings(paths: Paths) -> None:
    path = paths.raw / "export-plus/ExportUpgrades.json"
    data = json.loads(path.read_text())
    data["/Lotus/Upgrades/Mods/Rifle/WeaponDamageAmountMod"]["incompatibilityTags"] = "AOE"
    path.write_text(json.dumps(data))
    with pytest.raises(RefreshError, match="incompatibilityTags"):
        build(paths.raw, paths.reference)


def _drop_module_entries(paths: Paths) -> None:
    (paths.raw / "wiki/Module_Weapons_data_primary.lua").write_text("return {}")


def test_gun_without_fire_rate_fails(paths: Paths) -> None:
    """Lanka's DE fire rate is 0; without the module's no-delay rule it has no usable rate."""
    _drop_module_entries(paths)
    with pytest.raises(RefreshError, match="Lanka"):
        build(paths.raw, paths.reference)


def test_no_doubled_damage_words_in_built_text(paths: Paths) -> None:
    data = build(paths.raw, paths.reference)
    levels = [m.level_stats for m in data.mods] + [a.level_stats for a in data.arcanes]
    text = " ".join(s for entry in levels for lvl in entry for s in lvl)
    for word in ("Electricity Electric", "Cold Freeze", "Gas Extra"):
        assert word not in text


def test_hunter_munitions_text_names_slash(paths: Paths) -> None:
    mod = next(m for m in build(paths.raw, paths.reference).mods if m.name == "Hunter Munitions")
    assert "Slash on Critical" in mod.level_stats[-1][0]


def test_gun_arcanes_get_their_slot_from_wfcd(paths: Paths) -> None:
    arcanes = {a.name: a for a in build(paths.raw, paths.reference).arcanes}
    assert (arcanes["Primary Merciless"].category, arcanes["Primary Merciless"].weapon_type) == (
        Category.PRIMARY,
        None,
    )
    assert arcanes["Secondary Deadhead"].category == Category.SECONDARY
    assert (arcanes["Shotgun Vendetta"].category, arcanes["Shotgun Vendetta"].weapon_type) == (
        Category.PRIMARY,
        "Shotgun",
    )
    assert "Arcane Energize" not in arcanes  # Warframe arcane


def test_de_arcane_missing_in_wfcd_fails(paths: Paths) -> None:
    """Review 2 bug 3: a new DE arcane WFCD has not typed yet is never dropped silently."""
    path = paths.raw / "wfcd/Arcanes.json"
    data = json.loads(path.read_text())
    path.write_text(json.dumps([a for a in data if a["name"] != "Primary Merciless"]))
    with pytest.raises(RefreshError, match="PrimaryDamageOnKill"):
        build(paths.raw, paths.reference)


def test_arcane_listed_twice_in_wfcd_fails(paths: Paths) -> None:
    path = paths.raw / "wfcd/Arcanes.json"
    data = json.loads(path.read_text())
    path.write_text(json.dumps([*data, data[0]]))
    with pytest.raises(RefreshError, match="listed twice"):
        build(paths.raw, paths.reference)


def test_unknown_wfcd_arcane_type_fails(paths: Paths) -> None:
    path = paths.raw / "wfcd/Arcanes.json"
    data = json.loads(path.read_text())
    data[0]["type"] = "Archgun Arcane"
    path.write_text(json.dumps(data))
    with pytest.raises(RefreshError, match="Archgun Arcane"):
        build(paths.raw, paths.reference)


def test_fire_rate_error_names_the_field_that_works(paths: Paths) -> None:
    """Review bug 5: the advice must point at what the build reads (`exclude`)."""
    _drop_module_entries(paths)
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
    from app.pipeline.build.weapons import _attack

    dot = {
        "name": "Corrosive DoT",
        "speed": 0,
        "crit_chance": 0,
        "crit_mult": 1,
        "status_chance": 0,
        "damage": {"corrosive": 10},
    }
    assert _attack(dot, "Tysis", None).fire_rate is None


def test_allowed_conclave_mod_is_kept(paths: Paths) -> None:
    """Review 3 R10: Double Tap works outside Conclave, kept through `allow`."""
    names = {m.name for m in build(paths.raw, paths.reference).mods}
    assert "Double Tap" in names and "Comet Rounds" not in names


def test_mod_keeps_de_description(paths: Paths) -> None:
    """Review 3 R11: rules only in the description reach the parser."""
    mods = {m.name: m for m in build(paths.raw, paths.reference).mods}
    assert mods["Semi-Rifle Cannonade"].description == (
        "Only compatible with Semi-Auto Trigger. Fire Rate cannot be modified."
    )
    assert mods["Serration"].description == ""


def test_untyped_gun_mod_gets_category_from_compat_name(paths: Paths) -> None:
    """Review 4 P2: DE files Sniper Ammo Mutation under type `---`."""
    mods = {m.name: m for m in build(paths.raw, paths.reference).mods}
    assert mods["Sniper Ammo Mutation"].category == Category.PRIMARY
    assert "/Intermediate/" not in mods["Sniper Ammo Mutation"].unique_name


def test_arcane_class_limit_must_match_a_gun(paths: Paths) -> None:
    """Review 4 P3: a renamed WFCD class never leaves Shotgun Vendetta fitting nothing."""
    path = paths.raw / "wfcd/Primary.json"
    data = json.loads(path.read_text())
    for w in data:
        if w["type"] == "Shotgun":
            w["type"] = "Scattergun"
    path.write_text(json.dumps(data))
    with pytest.raises(RefreshError, match=r"Shotgun Vendetta \(Shotgun\)"):
        build(paths.raw, paths.reference)


def test_mods_and_sets_carry_parsed_effects(paths: Paths) -> None:
    data = build(paths.raw, paths.reference)
    mods = {m.name: m for m in data.mods}
    assert mods["Serration"].effects.support == Support.FULL
    assert mods["Serration"].effects.effects[0].value == 1.65
    hunter = mods["Hunter Munitions"].effects.effects[0]
    assert (hunter.stat, hunter.damage_type) == (Stat.FORCED_PROC, DamageType.SLASH)
    assert mods["Semi-Rifle Cannonade"].effects.requires_trigger == "SEMI"
    vigilante = next(s for s in data.mod_sets if s.unique_name.endswith("VigilanteSetMod"))
    assert len(vigilante.bonuses) == vigilante.num_upgrades == 6
    assert vigilante.bonuses[-1].effects[0].stat == Stat.CRIT_TIER_UPGRADE


def _override(paths: Paths, entries: dict[str, object]) -> None:
    path = paths.reference / "overrides.json"
    data = json.loads(path.read_text())
    data["entries"] = entries
    path.write_text(json.dumps(data))


def test_override_replaces_parsed_effects(paths: Paths) -> None:
    uid = "/Lotus/Upgrades/CosmeticEnhancers/Offensive/ShotgunMultishotAndReloadSpeedOnCloseKill"
    _override(
        paths,
        {
            uid: {
                "name": "Shotgun Vendetta",
                "verified": "2026-11-08",
                "note": "test",
                "effects": [
                    {"stat": "multishot", "value": 1.8, "trigger": "on_kill", "duration_s": 15}
                ],
            }
        },
    )
    arcane = next(a for a in build(paths.raw, paths.reference).arcanes if a.unique_name == uid)
    assert arcane.effects.support == Support.FULL and arcane.effects.unparsed == []
    assert arcane.effects.effects[0].trigger == Trigger.ON_KILL
    assert arcane.effects.note == "test"


def test_override_matching_nothing_fails(paths: Paths) -> None:
    _override(paths, {"/Lotus/Nope": {"name": "x", "verified": "2026-11-08", "support": "partial"}})
    with pytest.raises(RefreshError, match="/Lotus/Nope"):
        build(paths.raw, paths.reference)


def test_invalid_override_effect_fails(paths: Paths) -> None:
    uid = "/Lotus/Upgrades/Mods/Rifle/WeaponDamageAmountMod"
    _override(
        paths,
        {
            uid: {
                "name": "Serration",
                "verified": "2026-11-08",
                "effects": [{"stat": "element", "value": 1}],
            }
        },
    )
    with pytest.raises(RefreshError, match="damage_type required"):
        build(paths.raw, paths.reference)


def test_exilus_from_flag_and_reference(paths: Paths) -> None:
    uid = "/Lotus/Upgrades/Mods/Sets/Vigilante/PrimaryVigilanteArmamentsMod"
    mods = {m.unique_name: m for m in build(paths.raw, paths.reference).mods}
    assert not mods[uid].exilus
    path = paths.reference / "exilus.json"
    data = json.loads(path.read_text())
    data["mods"] = [{"id": uid, "name": "Vigilante Armaments", "verified": "2026-11-08"}]
    path.write_text(json.dumps(data))
    assert {m.unique_name: m for m in build(paths.raw, paths.reference).mods}[uid].exilus
    data["mods"] = [{"id": "/Nope", "name": "x", "verified": "2026-11-08"}]
    path.write_text(json.dumps(data))
    with pytest.raises(RefreshError, match="/Nope"):
        build(paths.raw, paths.reference)


def test_override_without_verified_fails(paths: Paths) -> None:
    uid = "/Lotus/Upgrades/Mods/Rifle/WeaponDamageAmountMod"
    _override(paths, {uid: {"name": "Serration", "support": "partial"}})
    with pytest.raises(RefreshError, match="verified"):
        build(paths.raw, paths.reference)


def test_support_full_override_clears_unparsed(paths: Paths) -> None:
    """Review: support full means the leftover text was reviewed as no damage effect."""
    mods = {m.name: m for m in build(paths.raw, paths.reference).mods}
    thunderbolt = mods["Thunderbolt"]
    assert thunderbolt.effects.unparsed
    _override(
        paths,
        {
            thunderbolt.unique_name: {
                "name": "x",
                "verified": "2026-11-08",
                "support": "full",
                "note": "n",
            }
        },
    )
    after = {m.name: m for m in build(paths.raw, paths.reference).mods}["Thunderbolt"]
    assert (after.effects.support, after.effects.unparsed) == (Support.FULL, [])
    assert after.effects.effects == thunderbolt.effects.effects


def test_exilus_entry_without_verified_fails(paths: Paths) -> None:
    path = paths.reference / "exilus.json"
    data = json.loads(path.read_text())
    data["mods"] = [{"id": "/Lotus/Upgrades/Mods/Rifle/WeaponDamageAmountMod", "name": "Serration"}]
    path.write_text(json.dumps(data))
    with pytest.raises(RefreshError, match="verified"):
        build(paths.raw, paths.reference)


def _weapons(paths: Paths) -> dict[str, Weapon]:
    return {w.name: w for w in build(paths.raw, paths.reference).weapons}


def test_lanka_has_no_delay_between_shots(paths: Paths) -> None:
    """Saved Fire_Rate: Lanka's rate is 1 / charge time; the module says FireRate = math.huge."""
    lanka = _weapons(paths)["Lanka"]
    assert lanka.fire_rate is None
    assert lanka.sniper_combo_min == 2


def test_forced_procs_per_attack_from_the_wiki_module(paths: Paths) -> None:
    epitaph = _weapons(paths)["Epitaph"]
    procs = {a.name: a.forced_procs for a in epitaph.attacks}
    assert procs == {
        "Charged Shot": [DamageType.IMPACT],
        "Uncharged Direct Hit": [DamageType.IMPACT],
        "Uncharged AoE": [DamageType.COLD],
    }
    assert epitaph.no_reload


def test_gun_missing_in_the_modules_has_unknown_forced_procs(paths: Paths) -> None:
    braton = _weapons(paths)["Braton Prime"]
    assert all(a.forced_procs is None for a in braton.attacks)
    assert not braton.no_reload


def test_beam_ramp_start_default_and_rows(paths: Paths) -> None:
    weapons = _weapons(paths)
    assert weapons["Phage"].beam_ramp_start == 0.7
    assert weapons["Convectrix"].beam_ramp_start == 0.6
    assert weapons["Embolist"].beam_ramp_start == 0.3
    assert weapons["Braton Prime"].beam_ramp_start is None  # not a beam


def _fire_rows(paths: Paths) -> tuple[Path, dict[str, Any]]:
    path = paths.reference / "fire_overrides.json"
    return path, json.loads(path.read_text())


def test_beam_ramp_start_on_a_non_beam_fails(paths: Paths) -> None:
    path, fire = _fire_rows(paths)
    fire["weapons"]["/Lotus/Weapons/Tenno/Rifle/BratonPrime"] = {
        "name": "Braton Prime",
        "beam_ramp_start": 0.5,
        "verified": "2026-11-08",
    }
    path.write_text(json.dumps(fire))
    with pytest.raises(RefreshError, match="non-beam"):
        build(paths.raw, paths.reference)


def test_fire_override_with_unknown_key_or_gun_fails(paths: Paths) -> None:
    path, fire = _fire_rows(paths)
    epitaph = "/Lotus/Weapons/Tenno/Pistols/TnWraitheSidearm/TnWraitheSidearmWeapon"
    fire["weapons"][epitaph]["reload"] = 0
    path.write_text(json.dumps(fire))
    with pytest.raises(RefreshError, match="unknown keys"):
        build(paths.raw, paths.reference)
    del fire["weapons"][epitaph]["reload"]
    fire["weapons"]["/Lotus/Weapons/Nope"] = {"name": "Nope", "verified": "2026-11-08"}
    path.write_text(json.dumps(fire))
    with pytest.raises(RefreshError, match="unknown guns"):
        build(paths.raw, paths.reference)


def test_module_attacks_must_match_wfcd(paths: Paths) -> None:
    module = paths.raw / "wiki/Module_Weapons_data_secondary.lua"
    module.write_text(module.read_text().replace('"Uncharged AoE"', '"Uncharged Cloud"'))
    with pytest.raises(RefreshError, match="differ from the wiki module"):
        build(paths.raw, paths.reference)


def test_unknown_forced_proc_fails(paths: Paths) -> None:
    module = paths.raw / "wiki/Module_Weapons_data_secondary.lua"
    module.write_text(module.read_text().replace('{ "Cold" }', '{ "Frostbite" }'))
    with pytest.raises(RefreshError, match="Frostbite"):
        build(paths.raw, paths.reference)


def test_direct_bonus_default_and_exceptions(paths: Paths) -> None:
    """Default: adding on direct attacks, none on AoE; exceptions from the table (Epitaph:
    multiplying on its projectiles, Condition_Overload_(Mechanic) catalog)."""
    attacks = {a.name: a.direct_bonus for a in _weapons(paths)["Epitaph"].attacks}
    assert attacks == {
        "Charged Shot": "multiplying",
        "Uncharged Direct Hit": "multiplying",
        "Uncharged AoE": "none",
    }
    braton = {a.name: a.direct_bonus for a in _weapons(paths)["Braton Prime"].attacks}
    assert braton["Normal Attack"] == "adding"


def test_direct_bonus_row_for_unknown_attack_fails(paths: Paths) -> None:
    path = paths.reference / "galvanized_behaviour.json"
    data = json.loads(path.read_text())
    epitaph = "/Lotus/Weapons/Tenno/Pistols/TnWraitheSidearm/TnWraitheSidearmWeapon"
    data["weapons"][epitaph]["attacks"]["Throw"] = "none"
    path.write_text(json.dumps(data))
    with pytest.raises(RefreshError, match="unknown attacks"):
        build(paths.raw, paths.reference)
