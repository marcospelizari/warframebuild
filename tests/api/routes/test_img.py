from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.gamedata.store import GameData

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData) -> TestClient:
    (tmp_path / "img/weapons").mkdir(parents=True)
    (tmp_path / "img/weapons/soma-prime.png").write_bytes(PNG)
    (tmp_path / "secret.txt").write_text("no")
    web = tmp_path / "missing"  # the frontend mount must not serve tmp_path either
    app = create_app(web_dist=web, data=gamedata, releases=tmp_path, img_dir=tmp_path / "img")
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
