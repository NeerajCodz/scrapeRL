"""Tests for memory API routes."""

import pytest
from fastapi.testclient import TestClient


class TestMemoryAPI:
    """Test memory API endpoints."""

    def test_store_memory_entry(self, client: TestClient) -> None:
        """Test POST /api/memory/store creates new memory entry."""
        payload = {
            "memory_type": "short_term",
            "content": {
                "observation": "User clicked login button",
                "action": "click",
            },
            "metadata": {"url": "https://example.com"},
            "episode_id": "ep_001",
            "agent_id": "agent_test",
        }

        response = client.post("/api/memory/store", json=payload)

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["memory_type"] == "short_term"
        assert data["content"] == payload["content"]
        assert data["episode_id"] == "ep_001"
        assert "timestamp" in data

    def test_store_memory_all_types(self, client: TestClient) -> None:
        """Test storing memory with all valid types."""
        valid_types = ["short_term", "working", "long_term", "shared"]

        for memory_type in valid_types:
            payload = {
                "memory_type": memory_type,
                "content": {"test": f"data for {memory_type}"},
            }

            response = client.post("/api/memory/store", json=payload)
            assert response.status_code == 201
            data = response.json()
            assert data["memory_type"] == memory_type

    def test_store_memory_invalid_type(self, client: TestClient) -> None:
        """Test storing memory with invalid type."""
        payload = {"memory_type": "invalid_type", "content": {"test": "data"}}

        response = client.post("/api/memory/store", json=payload)
        assert response.status_code == 422

    def test_get_memory_entry(self, client: TestClient) -> None:
        """Test GET /api/memory/{entry_id}."""
        # Store first
        payload = {
            "memory_type": "long_term",
            "content": {"knowledge": "test data"},
        }

        store_response = client.post("/api/memory/store", json=payload)
        assert store_response.status_code == 201
        entry_id = store_response.json()["id"]

        # Retrieve
        response = client.get(f"/api/memory/{entry_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == entry_id
        assert data["memory_type"] == "long_term"

    def test_get_nonexistent_memory(self, client: TestClient) -> None:
        """Test GET /api/memory/{entry_id} for non-existent."""
        response = client.get("/api/memory/nonexistent-id-12345")
        assert response.status_code == 404

    def test_delete_memory_entry(self, client: TestClient) -> None:
        """Test DELETE /api/memory/{entry_id}."""
        # Store first
        payload = {
            "memory_type": "short_term",
            "content": {"temporary": "data"},
        }

        store_response = client.post("/api/memory/store", json=payload)
        assert store_response.status_code == 201
        entry_id = store_response.json()["id"]

        # Delete
        response = client.delete(f"/api/memory/{entry_id}")
        assert response.status_code == 204

        # Verify deleted
        get_response = client.get(f"/api/memory/{entry_id}")
        assert get_response.status_code == 404

    def test_query_memory(self, client: TestClient) -> None:
        """Test POST /api/memory/query."""
        # Store some entries first
        for i in range(3):
            payload = {
                "memory_type": "short_term",
                "content": {"index": i, "data": f"test_{i}"},
            }
            client.post("/api/memory/store", json=payload)

        # Query
        query_payload = {"query": "test", "limit": 10}
        response = client.post("/api/memory/query", json=query_payload)

        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total_found" in data

    def test_get_memory_stats(self, client: TestClient) -> None:
        """Test GET /api/memory/stats/overview."""
        response = client.get("/api/memory/stats/overview")

        assert response.status_code == 200
        data = response.json()

        assert "short_term_count" in data
        assert "working_count" in data
        assert "long_term_count" in data
        assert "shared_count" in data
        assert "total_count" in data

    def test_clear_memory_layer(self, client: TestClient) -> None:
        """Test DELETE /api/memory/clear/{memory_type}."""
        # Store entries
        payload = {
            "memory_type": "short_term",
            "content": {"test": "data"},
        }
        client.post("/api/memory/store", json=payload)

        # Clear
        response = client.delete("/api/memory/clear/short_term")
        assert response.status_code == 204

    def test_consolidate_memory(self, client: TestClient) -> None:
        """Test POST /api/memory/consolidate."""
        # Store short-term entries
        for i in range(3):
            payload = {
                "memory_type": "short_term",
                "content": {"index": i},
            }
            client.post("/api/memory/store", json=payload)

        # Consolidate
        response = client.post("/api/memory/consolidate")

        assert response.status_code == 200
        data = response.json()
        assert "consolidated_count" in data
