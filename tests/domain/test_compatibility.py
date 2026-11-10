from app.domain.compatibility import fits

RIFLE = "/Lotus/Weapons/Tenno/Rifle/LotusRifle"
SHOTGUN = "/Lotus/Weapons/Tenno/Shotgun/LotusShotgun"
GUN = [RIFLE, "/Lotus/Weapons/Tenno/LotusLongGun"]


def test_mod_class_must_be_one_of_the_gun() -> None:
    """Shotgun_Mods:1: shotgun mods only on primary shotguns."""
    assert fits(GUN, ["PROJECTILE"], RIFLE, [], [])
    assert not fits(GUN, ["PROJECTILE"], SHOTGUN, [], [])


def test_needs_one_of_its_tags() -> None:
    """Sniper Ammo Mutation: SNIPER_AMMO or LAUNCHER_AMMO."""
    needs = ["LAUNCHER_AMMO", "SNIPER_AMMO"]
    assert fits(GUN, ["AOE", "SNIPER_AMMO"], RIFLE, needs, [])
    assert not fits(GUN, ["ASSAULT_AMMO"], RIFLE, needs, [])


def test_excluded_tag_blocks() -> None:
    """Split Flights on Lenz (CRPBOW): cannot be equipped (Split_Flights:47-56)."""
    excludes = ["CROSSBOW", "CRPBOW", "GRNBOW", "INFBOW", "OMICRUS", "POWER_WEAPON"]
    assert not fits(GUN, ["AOE", "CRPBOW", "PROJECTILE"], RIFLE, [], excludes)
    assert fits(GUN, ["PROJECTILE"], RIFLE, [], excludes)


def test_unknown_data_takes_only_untagged_mods() -> None:
    assert fits(GUN, None, RIFLE, [], [])
    assert not fits(GUN, None, RIFLE, [], ["SINGLESHOT"])
    assert not fits(GUN, ["PROJECTILE"], RIFLE, None, None)
    assert not fits(GUN, ["PROJECTILE"], None, [], [])
