"""Tests for observation model."""

import pytest
from app.core.observation import Observation, TaskContext, ExtractedField, MemoryContext


def test_observation_creation() -> None:
    """Test creating an observation."""
    obs = Observation(
        episode_id="ep_001",
        task_id="task_001",
        step_number=0,
    )
    assert obs.episode_id == "ep_001"
    assert obs.step_number == 0
    assert obs.extraction_progress == 0.0


def test_observation_with_task_context() -> None:
    """Test observation with task context."""
    task_ctx = TaskContext(
        task_id="task_001",
        task_name="Extract Product",
        task_type="extraction",
        target_fields=["name", "price"],
        required_fields=["name"],
    )
    obs = Observation(
        episode_id="ep_001",
        task_id="task_001",
        step_number=0,
        task_context=task_ctx,
    )
    assert obs.task_context is not None
    assert obs.task_context.task_name == "Extract Product"


def test_observation_extraction_tracking() -> None:
    """Test extraction progress tracking."""
    obs = Observation(
        episode_id="ep_001",
        task_id="task_001",
        step_number=1,
        extracted_so_far=[
            ExtractedField(field_name="name", value="Test Product", confidence=0.95),
        ],
        fields_remaining=["price", "description"],
    )
    assert len(obs.extracted_so_far) == 1
    assert obs.is_field_extracted("name")
    assert not obs.is_field_extracted("price")
    
    extraction_dict = obs.get_extraction_dict()
    assert extraction_dict["name"] == "Test Product"


def test_observation_context_summary() -> None:
    """Test context summary generation."""
    obs = Observation(
        episode_id="ep_001",
        task_id="task_001",
        step_number=5,
        current_url="https://example.com",
        extraction_progress=0.5,
        extracted_so_far=[
            ExtractedField(field_name="name", value="Test"),
        ],
        fields_remaining=["price"],
    )
    summary = obs.get_context_summary()
    assert "Step 5" in summary
    assert "example.com" in summary
