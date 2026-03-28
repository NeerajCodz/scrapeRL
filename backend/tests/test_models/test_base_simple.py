"""Simple tests to verify the base model structures."""

import pytest
from app.models.providers.base import (
    TokenUsage, 
    CompletionResponse,
    ModelInfo,
    ProviderError
)


def test_token_usage_creation():
    """Test TokenUsage creation and addition."""
    usage1 = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    usage2 = TokenUsage(prompt_tokens=5, completion_tokens=10, total_tokens=15)
    
    combined = usage1 + usage2
    assert combined.prompt_tokens == 15
    assert combined.completion_tokens == 30
    assert combined.total_tokens == 45


def test_completion_response_creation():
    """Test CompletionResponse creation."""
    usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    
    response = CompletionResponse(
        content="Hello world",
        model="test-model",
        provider="test-provider", 
        usage=usage,
        finish_reason="stop",
        cost=0.001
    )
    
    assert response.content == "Hello world"
    assert response.model == "test-model"
    assert response.provider == "test-provider"
    assert response.usage.total_tokens == 30
    assert response.cost == 0.001


def test_model_info_creation():
    """Test ModelInfo creation."""
    info = ModelInfo(
        id="test-model",
        name="Test Model", 
        provider="test",
        context_window=4096,
        max_output_tokens=1000,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.002
    )
    
    assert info.id == "test-model"
    assert info.context_window == 4096
    assert info.cost_per_million_input == 1.0
    assert info.cost_per_million_output == 2.0


def test_provider_error():
    """Test ProviderError creation."""
    error = ProviderError("Test error", "test-provider", 500)
    
    assert error.message == "Test error"
    assert error.provider == "test-provider"
    assert error.status_code == 500
    assert str(error) == "[test-provider] Test error"