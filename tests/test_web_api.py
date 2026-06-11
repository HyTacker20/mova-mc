"""Tests for the web API routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture()
def client() -> TestClient:
    app = create_app(dev=True)
    return TestClient(app, raise_server_exceptions=True)


class TestCatalog:
    def test_providers_returns_all_eight(self, client: TestClient) -> None:
        resp = client.get("/api/catalog/providers")
        assert resp.status_code == 200
        data = resp.json()
        ids = [p["id"] for p in data["providers"]]
        assert "google" in ids
        assert "openai" in ids
        assert "anthropic" in ids
        assert len(ids) == 8

    def test_google_does_not_require_key(self, client: TestClient) -> None:
        resp = client.get("/api/catalog/providers")
        providers = {p["id"]: p for p in resp.json()["providers"]}
        assert providers["google"]["requires_key"] is False

    def test_openai_has_models(self, client: TestClient) -> None:
        resp = client.get("/api/catalog/providers")
        providers = {p["id"]: p for p in resp.json()["providers"]}
        assert len(providers["openai"]["models"]) > 0


class TestMods:
    def test_nonexistent_path_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/mods", params={"path": "/does/not/exist/ever"})
        assert resp.status_code == 404

    def test_empty_dir_returns_empty_list(self, client: TestClient, tmp_path) -> None:
        resp = client.get("/api/mods", params={"path": str(tmp_path)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["mods"] == []
        assert data["total"] == 0
        assert data["selected"] == 0


class TestJobs:
    def test_create_job_with_no_mods_raises_422(self, client: TestClient, tmp_path) -> None:
        resp = client.post(
            "/api/jobs",
            json={
                "path": str(tmp_path),
                "source": "en_US",
                "target": "uk_UA",
                "provider": "google",
            },
        )
        assert resp.status_code == 422

    def test_get_unknown_job_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/jobs/nonexistent-id")
        assert resp.status_code == 404

    def test_cancel_unknown_job_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/jobs/nonexistent-id/cancel")
        assert resp.status_code == 404

    def test_events_unknown_job_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/jobs/nonexistent-id/events")
        assert resp.status_code == 404
