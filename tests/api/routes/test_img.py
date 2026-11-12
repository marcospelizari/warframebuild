from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.gamedata.images import picture_name
from app.gamedata.store import GameData

PNG = b"\x89PNG\r\n\x1a\n"
JPEG = b"\xff\xd8\xff\xe0"
WEBP = b"RIFF\x00\x00\x00\x00WEBP"


def serration(gamedata: GameData) -> str:
    mod = next(m for m in gamedata.mods.mods if m.name == "Serration")
    name = picture_name(mod.unique_name, mod.texture_location)
    assert name is not None
    return name


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData) -> TestClient:
    (tmp_path / "img/weapons").mkdir(parents=True)
    (tmp_path / "img/weapons/soma-prime.png").write_bytes(PNG)
    (tmp_path / "img/mods").mkdir()
    (tmp_path / "img/mods" / serration(gamedata)).write_bytes(JPEG)
    (tmp_path / "img/mods/0000000000000000.jpg").write_bytes(JPEG)  # cached, not in gamedata
    (tmp_path / "art/mod-card").mkdir(parents=True)
    (tmp_path / "art/mod-card/GoldFrameTop.webp").write_bytes(WEBP)
    (tmp_path / "art/secret.png").write_bytes(PNG)
    (tmp_path / "secret.txt").write_text("no")
    web = tmp_path / "missing"  # the frontend mount must not serve tmp_path either
    app = create_app(
        web_dist=web,
        data=gamedata,
        releases=tmp_path,
        img_dir=tmp_path / "img",
        art_dir=tmp_path / "art",
    )
    return TestClient(app)


def test_cached_icon_is_served_immutable(client: TestClient) -> None:
    response = client.get("/img/weapons/soma-prime.png")
    assert response.status_code == 200
    assert response.content == PNG
    assert "immutable" in response.headers["cache-control"]


@pytest.mark.parametrize(
    "name", ["lex-prime.png", "nope.png", "soma-prime", "..%2F..%2Fsecret.txt", "%2E%2E"]
)
def test_only_known_cached_icons(client: TestClient, name: str) -> None:
    """S2: the name is looked up, never joined into a path as given."""
    response = client.get(f"/img/weapons/{name}")
    assert response.status_code == 404
    assert response.content != b"no"


def test_known_mod_picture_is_served(client: TestClient, gamedata: GameData) -> None:
    response = client.get(f"/img/mods/{serration(gamedata)}")
    assert response.status_code == 200
    assert response.content == JPEG
    assert response.headers["content-type"] == "image/jpeg"
    assert "immutable" in response.headers["cache-control"]


@pytest.mark.parametrize(
    "path",
    [
        "/img/mods/0000000000000000.jpg",  # on disk but not a gamedata picture
        "/img/arcanes/0000000000000000.png",
        "/img/other/x.png",
        "/img/mods/..%2F..%2Fsecret.txt",
    ],
)
def test_only_gamedata_pictures(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert response.content not in (JPEG, b"no")


def test_card_art_from_known_folder(client: TestClient) -> None:
    response = client.get("/img/art/mod-card/GoldFrameTop.webp")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"


@pytest.mark.parametrize(
    "path",
    [
        "/img/art/mod-card/Missing.webp",
        "/img/art/other/GoldFrameTop.webp",  # folder not in the list
        "/img/art/mod-card/..%2Fsecret.png",
        "/img/art/..%2Fsecret.png/x.png",
        "/img/art/mod-card/a.b.png",
        "/img/art/mod-card/Madurai_Pol(xBlack).svg",  # no SVG
    ],
)
def test_card_art_only_plain_names_in_known_folders(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert response.content != PNG
