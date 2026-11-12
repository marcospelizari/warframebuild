from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.gamedata.store import GameData

INDEX = """<!doctype html><html><head>
<!-- page-meta --><title>warframeBuild</title><!-- /page-meta -->
</head><body><div id="root"></div></body></html>"""


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData, releases: Path) -> TestClient:
    (tmp_path / "web").mkdir()
    (tmp_path / "web/index.html").write_text(INDEX)
    app = create_app(web_dist=tmp_path / "web", data=gamedata, releases=releases)
    return TestClient(app)


def test_weapon_page_carries_its_own_title_and_preview_tags(client: TestClient) -> None:
    response = client.get("/w/soma-prime")
    assert response.status_code == 200
    page = response.text
    assert "<title>Soma Prime build: mods, forma, arcane | warframeBuild</title>" in page
    assert '<link rel="canonical" href="http://testserver/w/soma-prime" />' in page
    assert 'og:image" content="http://testserver/img/weapons/soma-prime.png"' in page
    assert 'name="description" content="Recommended Soma Prime build: ' in page
    assert "noindex" not in page
    assert '<div id="root"></div>' in page


def test_faction_page_names_the_faction(client: TestClient) -> None:
    page = client.get("/w/soma-prime/the-murmur").text
    assert "<title>Soma Prime build against The Murmur | warframeBuild</title>" in page
    assert 'href="http://testserver/w/soma-prime/the-murmur"' in page


def test_edited_build_is_not_indexed_and_points_to_the_plain_page(client: TestClient) -> None:
    page = client.get("/w/soma-prime?b=abc").text
    assert '<meta name="robots" content="noindex" />' in page
    assert 'rel="canonical" href="http://testserver/w/soma-prime"' in page


@pytest.mark.parametrize("path", ["/w/nope", "/w/soma-prime/nope", "/w/%3Cscript%3E"])
def test_unknown_gun_or_faction_is_a_real_404_with_the_app(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert '<div id="root"></div>' in response.text
    assert "noindex" in response.text
    assert "<script>" not in response.text


def test_gun_without_builds_in_the_release_still_gets_its_page(client: TestClient) -> None:
    page = client.get("/w/lex-prime").text  # not in the test release
    assert "<title>Lex Prime build: mods, forma, arcane | warframeBuild</title>" in page
    assert 'content="Calculated against level 120 Steel Path enemies."' in page


def test_faction_page_without_builds_is_not_a_404(tmp_path: Path, gamedata: GameData) -> None:
    (tmp_path / "web").mkdir()
    (tmp_path / "web/index.html").write_text(INDEX)
    app = create_app(web_dist=tmp_path / "web", data=gamedata, releases=tmp_path / "none")
    response = TestClient(app).get("/w/soma-prime/grineer")
    assert response.status_code == 200
    assert "<title>Soma Prime build | warframeBuild</title>" in response.text


def test_public_origin_wins_over_the_request_host(
    tmp_path: Path, gamedata: GameData, releases: Path
) -> None:
    (tmp_path / "web").mkdir()
    (tmp_path / "web/index.html").write_text(INDEX)
    app = create_app(
        web_dist=tmp_path / "web",
        data=gamedata,
        releases=releases,
        public_origin="https://builds.example/",
    )
    page = TestClient(app).get("/w/soma-prime", headers={"host": "evil.example"}).text
    assert '<link rel="canonical" href="https://builds.example/w/soma-prime" />' in page
    assert "evil.example" not in page


@pytest.mark.parametrize("bad", ["builds.example", "https://x.example/path", "javascript:x"])
def test_public_origin_must_be_scheme_and_host(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError, match="public origin"):
        create_app(web_dist=tmp_path, public_origin=bad)


def test_updates_page_carries_its_own_title(client: TestClient) -> None:
    page = client.get("/updates").text
    assert "<title>Game updates | warframeBuild</title>" in page
    assert '<link rel="canonical" href="http://testserver/updates" />' in page
