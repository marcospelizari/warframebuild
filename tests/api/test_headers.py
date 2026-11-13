"""Step 11 hardening: headers (S6), generic 500 (S7), caching and fallbacks, crawler files."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.headers import CACHE_FOREVER, CSP
from app.gamedata.store import GameData


def _app(tmp_path: Path, data: GameData, origin: str | None = None) -> FastAPI:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<p>app</p>" + "x" * 2000, encoding="utf-8")
    (dist / "assets/index-abc.js").write_text("console.log(1)", encoding="utf-8")
    return create_app(
        web_dist=dist, data=data, releases=tmp_path / "releases", public_origin=origin
    )


@pytest.fixture
def client(tmp_path: Path, gamedata: GameData) -> TestClient:
    return TestClient(_app(tmp_path, gamedata))


def test_every_answer_carries_the_security_headers(client: TestClient) -> None:
    for path in ("/", "/api/health", "/api/nothing", "/img/weapons/nothing.png"):
        headers = client.get(path).headers
        assert headers["content-security-policy"] == CSP, path
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert "strict-transport-security" not in headers  # no TLS known


def test_hsts_only_behind_an_https_origin(tmp_path: Path, gamedata: GameData) -> None:
    client = TestClient(_app(tmp_path, gamedata, "https://example.org"))
    assert client.get("/").headers["strict-transport-security"] == "max-age=31536000"


def test_hashed_assets_cache_forever_and_missing_files_stay_404(client: TestClient) -> None:
    assert client.get("/assets/index-abc.js").headers["cache-control"] == CACHE_FOREVER
    for path in ("/assets/index-old.js", "/img/nothing", "/api/nothing"):
        response = client.get(path)
        assert response.status_code == 404, path
        assert "immutable" not in response.headers.get("cache-control", "")
    assert client.get("/some/client/route").text.startswith("<p>app</p>")  # F1 fallback


def test_a_crash_answers_a_generic_500(tmp_path: Path, gamedata: GameData) -> None:
    app = create_app(web_dist=tmp_path / "none", data=gamedata, releases=tmp_path)  # no "/" mount

    def boom() -> None:
        raise RuntimeError("secret detail /var/home")

    app.add_api_route("/api/boom", boom)
    response = TestClient(app, raise_server_exceptions=False).get("/api/boom")
    assert response.status_code == 500
    assert response.headers["content-security-policy"] == CSP
    assert response.json() == {
        "code": "internal_error",
        "message": "Something went wrong on our side.",
        "field": None,
    }


def test_large_answers_are_compressed(client: TestClient) -> None:
    response = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert response.headers["content-encoding"] == "gzip"


def test_robots_and_sitemap_name_every_gun_page(tmp_path: Path, gamedata: GameData) -> None:
    client = TestClient(_app(tmp_path, gamedata, "https://example.org"))
    robots = client.get("/robots.txt")
    assert robots.text.endswith("Sitemap: https://example.org/sitemap.xml\n")
    sitemap = client.get("/sitemap.xml")
    assert sitemap.headers["content-type"].startswith("application/xml")
    assert "<loc>https://example.org/</loc>" in sitemap.text
    assert "<loc>https://example.org/w/soma-prime</loc>" in sitemap.text
    assert sitemap.text.count("<url>") == 1 + len(gamedata.weapons)
