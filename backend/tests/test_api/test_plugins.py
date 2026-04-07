"""Tests for plugins API routes."""

import pytest
from fastapi.testclient import TestClient


class TestPluginsAPI:
    """Test plugins API endpoints."""

    def test_list_all_plugins(self, client: TestClient) -> None:
        """Test GET /api/plugins returns all plugins."""
        response = client.get("/api/plugins")

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "plugins" in data
        assert "categories" in data
        assert "stats" in data

        # Check stats structure
        stats = data["stats"]
        assert "total" in stats
        assert "installed" in stats
        assert "available" in stats
        assert stats["total"] >= 0
        assert stats["installed"] >= 0
        assert stats["available"] >= 0

    def test_list_plugins_by_category(self, client: TestClient) -> None:
        """Test GET /api/plugins?category=apis filters by category."""
        response = client.get("/api/plugins?category=apis")

        assert response.status_code == 200
        data = response.json()

        # Should only contain the filtered category
        plugins = data["plugins"]
        if "apis" in plugins:
            # All plugins in the response should be from apis category
            for plugin in plugins["apis"]:
                assert plugin["category"] == "apis"

    def test_list_installed_plugins(self, client: TestClient) -> None:
        """Test GET /api/plugins/installed returns only installed plugins."""
        response = client.get("/api/plugins/installed")

        assert response.status_code == 200
        data = response.json()

        assert "plugins" in data
        assert "count" in data

        # All returned plugins should be installed
        for plugin in data["plugins"]:
            assert plugin["installed"] is True

        # Count should match number of plugins
        assert data["count"] == len(data["plugins"])

    def test_get_specific_plugin_exists(self, client: TestClient) -> None:
        """Test GET /api/plugins/{plugin_id} for existing plugin."""
        # First get list of plugins to find a valid ID
        list_response = client.get("/api/plugins")
        assert list_response.status_code == 200

        plugins_data = list_response.json()

        # Find first plugin from any category
        plugin_id = None
        for category, plugins in plugins_data["plugins"].items():
            if plugins:
                plugin_id = plugins[0]["id"]
                break

        if plugin_id:
            response = client.get(f"/api/plugins/{plugin_id}")
            assert response.status_code == 200

            data = response.json()
            assert data["id"] == plugin_id
            assert "name" in data
            assert "category" in data
            assert "installed" in data

    def test_get_nonexistent_plugin(self, client: TestClient) -> None:
        """Test GET /api/plugins/{plugin_id} for non-existent plugin."""
        response = client.get("/api/plugins/nonexistent-plugin")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_install_plugin_success(self, client: TestClient) -> None:
        """Test POST /api/plugins/install for valid plugin."""
        # First get a plugin that's not installed
        list_response = client.get("/api/plugins")
        assert list_response.status_code == 200

        plugins_data = list_response.json()

        # Find an uninstalled plugin
        plugin_id = None
        for category, plugins in plugins_data["plugins"].items():
            for plugin in plugins:
                if not plugin["installed"]:
                    plugin_id = plugin["id"]
                    break
            if plugin_id:
                break

        if plugin_id:
            payload = {"plugin_id": plugin_id}
            response = client.post("/api/plugins/install", json=payload)

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "success"
            assert data["plugin"]["id"] == plugin_id
            assert data["plugin"]["installed"] is True
            assert "installed successfully" in data["message"]

    def test_install_already_installed_plugin(self, client: TestClient) -> None:
        """Test installing a plugin that's already installed."""
        # First install a plugin
        list_response = client.get("/api/plugins")
        assert list_response.status_code == 200

        plugins_data = list_response.json()

        # Find an uninstalled plugin to install first
        plugin_id = None
        for category, plugins in plugins_data["plugins"].items():
            for plugin in plugins:
                if not plugin["installed"]:
                    plugin_id = plugin["id"]
                    break
            if plugin_id:
                break

        if plugin_id:
            # Install it
            payload = {"plugin_id": plugin_id}
            response = client.post("/api/plugins/install", json=payload)
            assert response.status_code == 200

            # Try to install again
            response = client.post("/api/plugins/install", json=payload)
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "already_installed"
            assert "already installed" in data["message"]

    def test_install_nonexistent_plugin(self, client: TestClient) -> None:
        """Test installing a non-existent plugin."""
        payload = {"plugin_id": "nonexistent-plugin"}
        response = client.post("/api/plugins/install", json=payload)

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_uninstall_plugin_success(self, client: TestClient) -> None:
        """Test POST /api/plugins/uninstall for installed non-core plugin."""
        # First install a non-core plugin
        list_response = client.get("/api/plugins")
        assert list_response.status_code == 200

        plugins_data = list_response.json()

        # Find a non-core plugin to install and then uninstall
        core_plugins = {
            "mcp-browser",
            "mcp-search",
            "mcp-html",
            "mcp-python-sandbox",
            "proc-json",
            "proc-python",
            "proc-pandas",
            "proc-numpy",
            "proc-bs4",
        }
        plugin_id = None

        for category, plugins in plugins_data["plugins"].items():
            for plugin in plugins:
                if plugin["id"] not in core_plugins and not plugin["installed"]:
                    plugin_id = plugin["id"]
                    break
            if plugin_id:
                break

        if plugin_id:
            # Install it first
            install_payload = {"plugin_id": plugin_id}
            install_response = client.post("/api/plugins/install", json=install_payload)
            assert install_response.status_code == 200

            # Now uninstall it
            uninstall_payload = {"plugin_id": plugin_id}
            response = client.post("/api/plugins/uninstall", json=uninstall_payload)

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "success"
            assert data["plugin"]["id"] == plugin_id
            assert data["plugin"]["installed"] is False
            assert "uninstalled successfully" in data["message"]

    def test_uninstall_core_plugin_forbidden(self, client: TestClient) -> None:
        """Test uninstalling core plugin is forbidden."""
        # Try to uninstall a core plugin
        core_plugin_id = "mcp-browser"  # This should be a core plugin
        payload = {"plugin_id": core_plugin_id}

        response = client.post("/api/plugins/uninstall", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "Cannot uninstall core plugin" in data["detail"]

    def test_uninstall_not_installed_plugin(self, client: TestClient) -> None:
        """Test uninstalling a plugin that's not installed."""
        # Find an uninstalled non-core plugin
        list_response = client.get("/api/plugins")
        assert list_response.status_code == 200

        plugins_data = list_response.json()
        core_plugins = {
            "mcp-browser",
            "mcp-search",
            "mcp-html",
            "mcp-python-sandbox",
            "proc-json",
            "proc-python",
            "proc-pandas",
            "proc-numpy",
            "proc-bs4",
        }

        plugin_id = None
        for category, plugins in plugins_data["plugins"].items():
            for plugin in plugins:
                if plugin["id"] not in core_plugins and not plugin["installed"]:
                    plugin_id = plugin["id"]
                    break
            if plugin_id:
                break

        if plugin_id:
            payload = {"plugin_id": plugin_id}
            response = client.post("/api/plugins/uninstall", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "not_installed"
            assert "not installed" in data["message"]

    def test_uninstall_nonexistent_plugin(self, client: TestClient) -> None:
        """Test uninstalling a non-existent plugin."""
        payload = {"plugin_id": "nonexistent-plugin"}
        response = client.post("/api/plugins/uninstall", json=payload)

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_categories(self, client: TestClient) -> None:
        """Test that plugins list includes categories."""
        response = client.get("/api/plugins")

        assert response.status_code == 200
        data = response.json()

        assert "categories" in data
        categories = data["categories"]

        assert isinstance(categories, list)
        assert len(categories) > 0

        # Categories are returned as strings (category IDs)
        expected_categories = ["apis", "mcps", "processors"]
        for expected in expected_categories:
            assert expected in categories

        # Agents/skills are intentionally managed via /api/agents, not /api/plugins
        assert "skills" not in categories

    def test_plugin_structure_validation(self, client: TestClient) -> None:
        """Test that all plugins have required fields."""
        response = client.get("/api/plugins")
        assert response.status_code == 200

        data = response.json()

        required_fields = ["id", "name", "category", "description", "version", "installed"]

        for category, plugins in data["plugins"].items():
            for plugin in plugins:
                for field in required_fields:
                    assert field in plugin, (
                        f"Plugin {plugin.get('id', 'unknown')} missing field {field}"
                    )

    def test_install_uninstall_payload_validation(self, client: TestClient) -> None:
        """Test payload validation for install/uninstall endpoints."""
        # Missing plugin_id for install
        response = client.post("/api/plugins/install", json={})
        assert response.status_code == 422

        # Missing plugin_id for uninstall
        response = client.post("/api/plugins/uninstall", json={})
        assert response.status_code == 422

        # Invalid payload type
        response = client.post("/api/plugins/install", json={"plugin_id": 123})
        assert response.status_code == 422

    def test_plugins_state_persistence(self, client: TestClient) -> None:
        """Test that plugin installation state persists across calls."""
        # Find a non-core plugin
        list_response = client.get("/api/plugins")
        assert list_response.status_code == 200

        plugins_data = list_response.json()
        core_plugins = {
            "mcp-browser",
            "mcp-search",
            "mcp-html",
            "mcp-python-sandbox",
            "proc-json",
            "proc-python",
            "proc-pandas",
            "proc-numpy",
            "proc-bs4",
        }

        plugin_id = None
        for category, plugins in plugins_data["plugins"].items():
            for plugin in plugins:
                if plugin["id"] not in core_plugins:
                    plugin_id = plugin["id"]
                    break
            if plugin_id:
                break

        if plugin_id:
            # Check initial state
            response = client.get(f"/api/plugins/{plugin_id}")
            initial_state = response.json()["installed"]

            # Toggle state by installing if not installed, or uninstalling if installed and not core
            if not initial_state:
                payload = {"plugin_id": plugin_id}
                response = client.post("/api/plugins/install", json=payload)
                assert response.status_code == 200

                # Verify state changed
                response = client.get(f"/api/plugins/{plugin_id}")
                assert response.json()["installed"] is True
            else:
                # If already installed and not core, uninstall
                if plugin_id not in core_plugins:
                    payload = {"plugin_id": plugin_id}
                    response = client.post("/api/plugins/uninstall", json=payload)
                    assert response.status_code == 200

                    # Verify state changed
                    response = client.get(f"/api/plugins/{plugin_id}")
                    assert response.json()["installed"] is False
