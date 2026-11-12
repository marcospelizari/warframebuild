import pytest

from app.gamedata.images import picture_name


def test_picture_name_is_stable_hash_plus_texture_type() -> None:
    name = picture_name(
        "/Lotus/Upgrades/Mods/Rifle/WeaponDamageAmountMod", "/a/b/Serration.png!00_x"
    )
    assert name is not None and name.endswith(".png") and len(name) == 20
    assert name == picture_name(
        "/Lotus/Upgrades/Mods/Rifle/WeaponDamageAmountMod", "/a/b/Serration.png!00_x"
    )
    assert picture_name("/x", "/a.jpeg!1") is not None
    assert str(picture_name("/x", "/a.jpeg!1")).endswith(".jpg")


def test_new_texture_gets_a_new_name() -> None:
    """A game update that changes the picture must not reuse the cached file or URL."""
    assert picture_name("/x", "/a.png!00_old") != picture_name("/x", "/a.png!00_new")
    assert picture_name("/x", "/a.png!1") != picture_name("/y", "/a.png!1")


@pytest.mark.parametrize("texture", [None, "", "/a/b.dds!00", "/no-extension"])
def test_no_picture_name_without_known_texture(texture: str | None) -> None:
    assert picture_name("/x", texture) is None
