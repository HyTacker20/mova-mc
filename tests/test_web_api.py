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
    def test_path_outside_allowed_roots_returns_400(self, client: TestClient) -> None:
        resp = client.get("/api/mods", params={"path": "/does/not/exist/ever"})
        assert resp.status_code == 400

    def test_nonexistent_path_returns_404(self, client: TestClient, tmp_path) -> None:
        nonexistent = tmp_path / "nonexistent_dir"
        resp = client.get("/api/mods", params={"path": str(nonexistent)})
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


class TestConfig:
    def test_get_config_no_file_returns_defaults(self, client: TestClient, tmp_path) -> None:
        resp = client.get("/api/config", params={"path": str(tmp_path)})
        assert resp.status_code == 200
        data = resp.json()
        # CWD fallback may find the project's own movamc.toml — that's fine.
        # The endpoint always returns 200 with sensible defaults.
        assert "provider" in data
        assert "model" in data
        assert "source" in data

    def test_save_and_load_config_roundtrip(self, client: TestClient, tmp_path) -> None:
        # Save
        resp = client.post(
            "/api/config",
            json={"provider": "openai", "model": "gpt-4o", "mods_path": str(tmp_path)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["config_path"] is not None

        # Load back
        resp = client.get("/api/config", params={"path": str(tmp_path)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4o"
        assert data["config_path"] is not None

    def test_save_merges_with_existing(self, client: TestClient, tmp_path) -> None:
        # Save provider first
        client.post("/api/config", json={"provider": "openai", "mods_path": str(tmp_path)})

        # Then save model only — should keep provider
        resp = client.post(
            "/api/config",
            json={"model": "gpt-4o-mini", "mods_path": str(tmp_path)},
        )
        assert resp.status_code == 200

        # Verify both persisted
        get_resp = client.get("/api/config", params={"path": str(tmp_path)})
        data = get_resp.json()
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4o-mini"

    def test_config_qa_roundtrip(self, client: TestClient, tmp_path) -> None:
        resp = client.post(
            "/api/config",
            json={
                "mods_path": str(tmp_path),
                "qa": {
                    "judge": True,
                    "judge_provider": "opencode",
                    "judge_model": "deepseek-v4-flash",
                    "threshold": 4,
                    "max_attempts": 3,
                },
            },
        )
        assert resp.status_code == 200

        get_resp = client.get("/api/config", params={"path": str(tmp_path)})
        assert get_resp.status_code == 200
        qa = get_resp.json()["qa"]
        assert qa["judge"] is True
        assert qa["judge_provider"] == "opencode"
        assert qa["judge_model"] == "deepseek-v4-flash"
        assert qa["threshold"] == 4
        assert qa["max_attempts"] == 3


class TestJobQaMapping:
    def test_job_qa_settings_applied(self) -> None:
        from app.core.settings import Settings

        from backend.schemas import JobRequest, QaRequest

        req = JobRequest(
            path="./mods",
            selected_mods=["test-mod"],
            qa=QaRequest(
                enabled=True,
                provider="opencode",
                model="deepseek-v4-flash",
            ),
        )
        settings = Settings(config_data=req.to_settings_dict())
        assert settings.qa.enabled is True
        assert settings.qa.provider == "opencode"
        assert settings.qa.model == "deepseek-v4-flash"
