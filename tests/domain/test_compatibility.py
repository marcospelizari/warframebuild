from app.domain.compatibility import fits


def test_untagged_mod_fits_any_gun() -> None:
    assert fits(["PROJECTILE"], [], [])
    assert fits([], [], [])


def test_needs_one_of_its_tags() -> None:
    """Sniper Ammo Mutation: SNIPER_AMMO or LAUNCHER_AMMO."""
    needs = ["LAUNCHER_AMMO", "SNIPER_AMMO"]
    assert fits(["AOE", "SNIPER_AMMO"], needs, [])
    assert not fits(["ASSAULT_AMMO"], needs, [])


def test_excluded_tag_blocks() -> None:
    """Split Flights on Lenz (CRPBOW): cannot be equipped (Split_Flights:47-56)."""
    excludes = ["CROSSBOW", "CRPBOW", "GRNBOW", "INFBOW", "OMICRUS", "POWER_WEAPON"]
    assert not fits(["AOE", "CRPBOW", "PROJECTILE"], [], excludes)
    assert fits(["PROJECTILE"], [], excludes)


def test_unknown_tags_take_only_untagged_mods() -> None:
    assert fits(None, [], [])
    assert not fits(None, [], ["SINGLESHOT"])
    assert not fits(["PROJECTILE"], None, None)
