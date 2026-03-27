"""Tests for action model."""

import pytest
from app.core.action import Action, ActionType


def test_action_creation() -> None:
    """Test creating an action."""
    action = Action(
        action_type=ActionType.EXTRACT_FIELD,
        parameters={"field_name": "price", "selector": ".price"},
        confidence=0.9,
    )
    assert action.action_type == ActionType.EXTRACT_FIELD
    assert action.confidence == 0.9


def test_action_factory_methods() -> None:
    """Test action factory methods."""
    nav_action = Action.navigate("https://example.com")
    assert nav_action.action_type == ActionType.NAVIGATE
    assert nav_action.parameters["url"] == "https://example.com"
    
    extract_action = Action.extract_field("price", ".product-price")
    assert extract_action.action_type == ActionType.EXTRACT_FIELD
    assert extract_action.parameters["field_name"] == "price"
    
    done_action = Action.done(success=True, message="Task completed")
    assert done_action.action_type == ActionType.DONE
    assert done_action.parameters["success"] is True


def test_action_validation() -> None:
    """Test action parameter validation."""
    # Valid action
    action = Action(
        action_type=ActionType.NAVIGATE,
        parameters={"url": "https://example.com"},
    )
    errors = action.validate_params()
    assert len(errors) == 0
    
    # Invalid action - missing required param
    invalid_action = Action(
        action_type=ActionType.NAVIGATE,
        parameters={},
    )
    errors = invalid_action.validate_params()
    assert len(errors) > 0
    assert "url" in errors[0]


def test_action_confidence_bounds() -> None:
    """Test confidence is bounded to 0-1 by Pydantic validation."""
    import pytest
    from pydantic import ValidationError
    
    # Values > 1.0 should raise validation error
    with pytest.raises(ValidationError):
        Action(
            action_type=ActionType.WAIT,
            confidence=1.5,
        )
    
    # Values < 0.0 should raise validation error
    with pytest.raises(ValidationError):
        Action(
            action_type=ActionType.WAIT,
            confidence=-0.5,
        )
    
    # Valid boundary values should work
    action_max = Action(action_type=ActionType.WAIT, confidence=1.0)
    assert action_max.confidence == 1.0
    
    action_min = Action(action_type=ActionType.WAIT, confidence=0.0)
    assert action_min.confidence == 0.0
