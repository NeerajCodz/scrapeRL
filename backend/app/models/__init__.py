"""Models module - LLM providers, routing, and ensemble capabilities."""

from app.models.router import (
    SmartModelRouter,
    RoutingStrategy,
    RoutingConfig,
    CostTracker,
    ModelScore,
)
from app.models.ensemble import (
    ModelEnsemble,
    AggregationStrategy,
    EnsembleResult,
)
from app.models.providers import (
    # Base
    BaseProvider,
    ProviderError,
    RateLimitError,
    ModelNotFoundError,
    CompletionResponse,
    ModelInfo,
    TokenUsage,
    # Providers
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    GroqProvider,
)
from app.models.providers.base import TaskType

__all__ = [
    # Router
    "SmartModelRouter",
    "RoutingStrategy",
    "RoutingConfig",
    "CostTracker",
    "ModelScore",
    "TaskType",
    # Ensemble
    "ModelEnsemble",
    "AggregationStrategy",
    "EnsembleResult",
    # Base
    "BaseProvider",
    "ProviderError",
    "RateLimitError",
    "ModelNotFoundError",
    "CompletionResponse",
    "ModelInfo",
    "TokenUsage",
    # Providers
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    "GroqProvider",
]
