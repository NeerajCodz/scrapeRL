"""Tests for tasks API routes."""

import pytest
from fastapi.testclient import TestClient


class TestTasksAPI:
    """Test tasks API endpoints."""

    def test_list_tasks(self, client: TestClient) -> None:
        """Test GET /api/tasks/ returns task list."""
        response = client.get("/api/tasks/")

        assert response.status_code == 200
        data = response.json()

        assert "tasks" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["tasks"], list)

    def test_list_tasks_pagination(self, client: TestClient) -> None:
        """Test task list pagination."""
        response = client.get("/api/tasks/?page=1&page_size=2")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_list_tasks_filter_by_difficulty(self, client: TestClient) -> None:
        """Test filtering tasks by difficulty."""
        response = client.get("/api/tasks/?difficulty=easy")

        assert response.status_code == 200
        data = response.json()
        for task in data["tasks"]:
            assert task["difficulty"] == "easy"

    def test_list_tasks_filter_by_type(self, client: TestClient) -> None:
        """Test filtering tasks by type."""
        response = client.get("/api/tasks/?task_type=single_page")

        assert response.status_code == 200
        data = response.json()
        for task in data["tasks"]:
            assert task["task_type"] == "single_page"

    def test_list_tasks_filter_by_tag(self, client: TestClient) -> None:
        """Test filtering tasks by tag."""
        response = client.get("/api/tasks/?tag=ecommerce")

        assert response.status_code == 200
        data = response.json()
        for task in data["tasks"]:
            assert "ecommerce" in task["tags"]

    def test_get_task_by_id(self, client: TestClient) -> None:
        """Test GET /api/tasks/{task_id}."""
        response = client.get("/api/tasks/task_001")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "task_001"
        assert "name" in data
        assert "description" in data
        assert "fields_to_extract" in data

    def test_get_nonexistent_task(self, client: TestClient) -> None:
        """Test GET /api/tasks/{task_id} for non-existent task."""
        response = client.get("/api/tasks/nonexistent-task-id")
        assert response.status_code == 404

    def test_create_task(self, client: TestClient) -> None:
        """Test POST /api/tasks/ creates a new task."""
        import uuid
        task_id = f"test_task_{uuid.uuid4().hex[:8]}"

        payload = {
            "id": task_id,
            "name": "Test Task",
            "description": "A test scraping task",
            "task_type": "single_page",
            "difficulty": "easy",
            "target_url": "https://example.com/test",
            "fields_to_extract": [
                {
                    "name": "title",
                    "description": "Page title",
                    "field_type": "string",
                    "required": True,
                }
            ],
            "success_criteria": {"min_accuracy": 0.8},
        }

        response = client.post("/api/tasks/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == task_id
        assert data["name"] == "Test Task"

    def test_create_duplicate_task(self, client: TestClient) -> None:
        """Test creating duplicate task returns conflict."""
        payload = {
            "id": "task_001",  # Existing task ID
            "name": "Duplicate Task",
            "description": "Should conflict",
            "task_type": "single_page",
            "difficulty": "easy",
            "fields_to_extract": [
                {"name": "test", "description": "test"}
            ],
            "success_criteria": {},
        }

        response = client.post("/api/tasks/", json=payload)
        assert response.status_code == 409

    def test_get_task_types(self, client: TestClient) -> None:
        """Test GET /api/tasks/types/ returns task types."""
        response = client.get("/api/tasks/types/")

        assert response.status_code == 200
        data = response.json()
        assert "task_types" in data
        assert "difficulties" in data
        assert "single_page" in data["task_types"]
        assert "easy" in data["difficulties"]
