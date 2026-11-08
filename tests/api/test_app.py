from importlib.metadata import version
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app


def test_health_reports_package_version(tmp_path: Path) -> None:
    client = TestClient(create_app(web_dist=tmp_path / "missing"))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": version("warframebuild")}


def test_serves_built_frontend(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>placeholder</h1>", encoding="utf-8")
    client = TestClient(create_app(web_dist=tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    assert "placeholder" in response.text


def test_missing_frontend_is_503(tmp_path: Path) -> None:
    client = TestClient(create_app(web_dist=tmp_path / "missing"))
    assert client.get("/").status_code == 503


def test_no_docs_exposed(tmp_path: Path) -> None:
    client = TestClient(create_app(web_dist=tmp_path / "missing"))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
