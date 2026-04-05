"""Tests for agent module catalog/install endpoints."""

from fastapi.testclient import TestClient

from app.api.routes import agents as agents_routes


def _reset_agent_modules() -> None:
    """Reset installed modules to deterministic defaults."""

    agents_routes._installed_agent_modules.clear()
    agents_routes._installed_agent_modules.update(agents_routes._DEFAULT_AGENT_MODULES)


def test_agent_catalog_includes_default_and_optional(client: TestClient) -> None:
    """Catalog should expose installed state for default and optional agents."""

    _reset_agent_modules()
    response = client.get("/api/agents/catalog")
    assert response.status_code == 200
    data = response.json()

    assert "agents" in data
    assert "stats" in data
    assert data["stats"]["total"] >= 2

    by_id = {agent["id"]: agent for agent in data["agents"]}
    assert by_id["planner-agent"]["installed"] is True
    assert by_id["planner-agent"]["default"] is True
    assert by_id["research-agent"]["installed"] is False
    assert by_id["research-agent"]["default"] is False


def test_install_and_uninstall_optional_agent_module(client: TestClient) -> None:
    """Optional agent modules can be installed and removed."""

    _reset_agent_modules()

    install_response = client.post("/api/agents/install", json={"agent_id": "research-agent"})
    assert install_response.status_code == 200
    assert install_response.json()["status"] == "success"

    installed_response = client.get("/api/agents/installed")
    assert installed_response.status_code == 200
    installed_ids = {agent["id"] for agent in installed_response.json()["agents"]}
    assert "research-agent" in installed_ids

    uninstall_response = client.post("/api/agents/uninstall", json={"agent_id": "research-agent"})
    assert uninstall_response.status_code == 200
    assert uninstall_response.json()["status"] == "success"


def test_uninstall_default_agent_module_forbidden(client: TestClient) -> None:
    """Default modules cannot be uninstalled."""

    _reset_agent_modules()
    response = client.post("/api/agents/uninstall", json={"agent_id": "planner-agent"})
    assert response.status_code == 400
    assert "Cannot uninstall default agent module" in response.json()["detail"]
