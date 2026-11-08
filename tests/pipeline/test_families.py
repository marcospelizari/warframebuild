"""Mod families (V4): derived from DE uniqueName stems and names, corrected by hand."""

import pytest

from app.pipeline.build.families import derive, stem
from app.pipeline.errors import RefreshError

R = "/Lotus/Upgrades/Mods/Rifle/"
MODS = [
    {"uniqueName": R + "WeaponFireIterationsMod", "name": "Split Chamber"},
    {"uniqueName": R + "WeaponFireIterationsSPMod", "name": "Galvanized Chamber"},
    {"uniqueName": R + "Expert/WeaponFreezeDamageModExpert", "name": "Primed Cryo Rounds"},
    {"uniqueName": R + "WeaponFreezeDamageMod", "name": "Cryo Rounds"},
    {"uniqueName": R + "WeaponDamageAmountMod", "name": "Serration"},
    {
        "uniqueName": "/Lotus/Upgrades/Mods/DualSource/Rifle/SerratedRushMod",
        "name": "Amalgam Serration",
    },
    {
        "uniqueName": "/Lotus/Upgrades/Mods/Sets/Vigilante/PrimaryVigilanteArmamentsMod",
        "name": "Vigilante Armaments",
    },
]


def test_stem_drops_variant_suffixes() -> None:
    assert stem(R + "WeaponFireIterationsSPMod") == "WeaponFireIterationsMod"
    assert stem(R + "Expert/WeaponFreezeDamageModExpert") == "WeaponFreezeDamageMod"


def test_derived_families() -> None:
    families = derive(MODS, {})
    assert families[R + "WeaponFireIterationsSPMod"] == families[R + "WeaponFireIterationsMod"]
    assert families[R + "WeaponFireIterationsMod"] == "WeaponFireIterationsMod"
    assert families[R + "Expert/WeaponFreezeDamageModExpert"] == "WeaponFreezeDamageMod"
    amalgam = "/Lotus/Upgrades/Mods/DualSource/Rifle/SerratedRushMod"
    assert families[amalgam] == families[R + "WeaponDamageAmountMod"] == "WeaponDamageAmountMod"
    assert "/Lotus/Upgrades/Mods/Sets/Vigilante/PrimaryVigilanteArmamentsMod" not in families


def test_corrections_join_and_split() -> None:
    vigilante = "/Lotus/Upgrades/Mods/Sets/Vigilante/PrimaryVigilanteArmamentsMod"
    families = derive(
        MODS,
        {
            "join": [
                {
                    "id": "j",
                    "mods": [R + "WeaponFireIterationsMod", vigilante],
                    "verified": "2026-11-08",
                }
            ],
            "split": [
                {"id": "s", "mods": [R + "WeaponFireIterationsSPMod"], "verified": "2026-11-08"}
            ],
        },
    )
    assert families[vigilante] == families[R + "WeaponFireIterationsMod"]
    assert R + "WeaponFireIterationsSPMod" not in families


def test_correction_with_unknown_mod_fails() -> None:
    with pytest.raises(RefreshError, match="Nope"):
        derive(
            MODS,
            {
                "join": [
                    {
                        "id": "x",
                        "mods": [R + "WeaponFireIterationsMod", "/Nope"],
                        "verified": "2026-11-08",
                    }
                ]
            },
        )


def test_correction_without_verified_fails() -> None:
    """Review: unverified corrections would never be listed for re-check."""
    with pytest.raises(RefreshError, match="verified"):
        derive(MODS, {"join": [{"id": "x", "mods": [R + "WeaponFireIterationsMod"]}]})


def test_real_fixture_mods_get_families(paths) -> None:  # type: ignore[no-untyped-def]
    from app.pipeline.build import build

    mods = {m.name: m for m in build(paths.raw, paths.reference).mods}
    assert mods["Serration"].family == "WeaponDamageAmountMod"
    assert mods["Vigilante Armaments"].family is None


def test_prefixed_name_ending_with_a_mod_name_is_its_variant() -> None:
    """Marcos 2026-11-08: a mod carrying the normal version's name cannot be equipped with it."""
    p = "/Lotus/Upgrades/Mods/Pistol/"
    mods = [
        *MODS,
        {"uniqueName": R + "WeaponPunctureDepthMod", "name": "Metal Auger"},
        {"uniqueName": R + "ArgonakAmalgamMod", "name": "Amalgam Argonak Metal Auger"},
        {"uniqueName": R + "InvisibleDamageMod", "name": "Spectral Serration"},
        {"uniqueName": p + "WeaponPunctureDepthMod", "name": "Seeker"},
        {"uniqueName": "/Lotus/Upgrades/Mods/Sets/Augur/AugurSeekerMod", "name": "Augur Seeker"},
        {
            "uniqueName": "/Lotus/Upgrades/Mods/Shotgun/SweepingSerrationMod",
            "name": "Sweeping Serration",
        },
    ]
    families = derive(mods, {})
    assert families[R + "ArgonakAmalgamMod"] == families[R + "WeaponPunctureDepthMod"]
    assert families[R + "InvisibleDamageMod"] == families[R + "WeaponDamageAmountMod"]
    assert "/Lotus/Upgrades/Mods/Sets/Augur/AugurSeekerMod" not in families
    assert "/Lotus/Upgrades/Mods/Shotgun/SweepingSerrationMod" not in families


def test_checked_joins_in_reference_apply(paths) -> None:  # type: ignore[no-untyped-def]
    from app.pipeline.build import build

    mods = {m.name: m for m in build(paths.raw, paths.reference).mods}
    assert mods["Primed Chamber"].family == mods["Charged Chamber"].family is not None
    assert mods["Galvanized Aptitude"].family == mods["Rifle Aptitude"].family is not None
