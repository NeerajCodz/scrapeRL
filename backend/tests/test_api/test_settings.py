"""Tests for settings API routes."""

import pytest
from fastapi.testclient import TestClient


class TestSettingsAPI:
    """Test settings API endpoints."""

    def test_get_settings_returns_default_config(self, client: TestClient) -> None:
        """Test GET /api/settings returns default configuration."""
        response = client.get("/api/settings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "api_keys_configured" in data
        assert "selected_model" in data
        assert "available_models" in data
        assert "plugins_installed" in data
        
        # Check default values
        assert data["selected_model"]["provider"] == "groq"
        assert data["selected_model"]["model"] == "gpt-oss-120b"
        assert isinstance(data["api_keys_configured"], dict)
        assert isinstance(data["available_models"], list)
        assert isinstance(data["plugins_installed"], list)

    def test_update_api_key_valid_provider(self, client: TestClient) -> None:
        """Test POST /api/settings/api-key with valid provider."""
        test_key = "test-key-12345"
        payload = {
            "provider": "openai",
            "api_key": test_key
        }
        
        response = client.post("/api/settings/api-key", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["provider"] == "openai"
        assert data["configured"] is True
        assert "set" in data["message"]

    def test_update_api_key_clear_key(self, client: TestClient) -> None:
        """Test POST /api/settings/api-key to clear API key."""
        payload = {
            "provider": "anthropic",
            "api_key": None
        }
        
        response = client.post("/api/settings/api-key", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["provider"] == "anthropic"
        assert data["configured"] is False
        assert "cleared" in data["message"]

    def test_update_api_key_invalid_provider(self, client: TestClient) -> None:
        """Test POST /api/settings/api-key with invalid provider."""
        payload = {
            "provider": "invalid_provider",
            "api_key": "test-key"
        }
        
        response = client.post("/api/settings/api-key", json=payload)
        
        assert response.status_code == 400
        data = response.json()
        assert "Unknown provider" in data["detail"]

    def test_select_model_valid_model(self, client: TestClient) -> None:
        """Test POST /api/settings/model with valid model."""
        payload = {
            "provider": "openai",
            "model": "gpt-4o"
        }
        
        response = client.post("/api/settings/model", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["selected_model"]["provider"] == "openai"
        assert data["selected_model"]["model"] == "gpt-4o"
        assert "Model set to" in data["message"]

    def test_select_model_invalid_model(self, client: TestClient) -> None:
        """Test POST /api/settings/model with invalid model."""
        payload = {
            "provider": "invalid_provider",
            "model": "invalid_model"
        }
        
        response = client.post("/api/settings/model", json=payload)
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid model" in data["detail"]

    def test_check_api_key_required_default(self, client: TestClient) -> None:
        """Test GET /api/settings/api-key/required returns default status."""
        response = client.get("/api/settings/api-key/required")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "required" in data
        assert "provider" in data
        assert "model" in data
        assert isinstance(data["required"], bool)

    def test_settings_persistence_across_calls(self, client: TestClient) -> None:
        """Test that settings persist across multiple API calls."""
        # Set an API key
        api_key_payload = {
            "provider": "google",
            "api_key": "test-google-key"
        }
        response = client.post("/api/settings/api-key", json=api_key_payload)
        assert response.status_code == 200
        
        # Select a model
        model_payload = {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-20241022"
        }
        response = client.post("/api/settings/model", json=model_payload)
        assert response.status_code == 200
        
        # Check that both changes are reflected in settings
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        
        # Model should be updated
        assert data["selected_model"]["provider"] == "anthropic"
        assert data["selected_model"]["model"] == "claude-3-5-sonnet-20241022"
        
        # API key should be configured (we don't expose actual keys)
        assert "google" in data["api_keys_configured"]

    def test_api_key_payload_validation(self, client: TestClient) -> None:
        """Test API key payload validation."""
        # Missing provider - should fail validation
        response = client.post("/api/settings/api-key", json={"api_key": "test"})
        assert response.status_code == 422

    def test_model_payload_validation(self, client: TestClient) -> None:
        """Test model selection payload validation."""
        # Missing provider
        response = client.post("/api/settings/model", json={"model": "gpt-4"})
        assert response.status_code == 422
        
        # Missing model
        response = client.post("/api/settings/model", json={"provider": "openai"})
        assert response.status_code == 422

    def test_all_providers_supported(self, client: TestClient) -> None:
        """Test that all expected providers are supported."""
        expected_providers = ["openai", "anthropic", "google", "groq"]
        
        for provider in expected_providers:
            payload = {
                "provider": provider,
                "api_key": f"test-{provider}-key"
            }
            response = client.post("/api/settings/api-key", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            assert data["provider"] == provider
            assert data["status"] == "success"

    def test_available_models_structure(self, client: TestClient) -> None:
        """Test that available models have expected structure."""
        response = client.get("/api/settings")
        assert response.status_code == 200
        
        data = response.json()
        models = data["available_models"]
        
        assert isinstance(models, list)
        assert len(models) > 0
        
        # Check structure of first model
        first_model = models[0]
        assert "provider" in first_model
        assert "model" in first_model
        assert isinstance(first_model["provider"], str)
        assert isinstance(first_model["model"], str)

    def test_api_keys_configured_structure(self, client: TestClient) -> None:
        """Test api_keys_configured returns all expected providers."""
        response = client.get("/api/settings")
        assert response.status_code == 200
        
        data = response.json()
        api_keys = data["api_keys_configured"]
        
        expected_providers = ["openai", "anthropic", "google", "groq"]
        for provider in expected_providers:
            assert provider in api_keys
            assert isinstance(api_keys[provider], bool)