"""Smart model router for intelligent model selection and fallback."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import SecretStr

from app.models.providers.base import (
    BaseProvider,
    CompletionResponse,
    ModelInfo,
    ProviderError,
    RateLimitError,
    TaskType,
    TokenUsage,
)
from app.models.providers.openai import OpenAIProvider
from app.models.providers.anthropic import AnthropicProvider
from app.models.providers.google import GoogleProvider
from app.models.providers.groq import GroqProvider
from app.models.providers.nvidia import NVIDIAProvider

logger = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    """Model routing strategies."""

    BEST_QUALITY = "best_quality"  # Use highest quality model
    BEST_SPEED = "best_speed"  # Use fastest model
    BEST_VALUE = "best_value"  # Balance quality/cost
    LOWEST_COST = "lowest_cost"  # Use cheapest model
    ROUND_ROBIN = "round_robin"  # Rotate between models


@dataclass
class ModelScore:
    """Scoring for model routing decisions."""

    model_id: str
    provider: str
    quality_score: float = 0.0  # 0-1, higher is better
    speed_score: float = 0.0  # 0-1, higher is faster
    cost_score: float = 0.0  # 0-1, higher is cheaper
    overall_score: float = 0.0


@dataclass
class RoutingConfig:
    """Configuration for model routing."""

    default_strategy: RoutingStrategy = RoutingStrategy.BEST_VALUE
    max_fallback_attempts: int = 3
    fallback_delay_seconds: float = 1.0
    enable_caching: bool = True
    cache_ttl_seconds: int = 300

    # Task-specific model preferences
    task_preferences: dict[TaskType, list[str]] = field(default_factory=lambda: {
        TaskType.GENERAL: ["gpt-4o", "claude-3-5-sonnet-20241022", "gemini-2.5-pro", "deepseek-r1"],
        TaskType.CODE: ["claude-3-5-sonnet-20241022", "gpt-4o", "devstral-2-123b", "gemini-2.5-pro"],
        TaskType.REASONING: ["claude-3-opus-20240229", "deepseek-r1", "gpt-4o", "step-3.5-flash"],
        TaskType.EXTRACTION: ["gpt-4o-mini", "claude-3-haiku-20240307", "gemini-2.5-flash"],
        TaskType.SUMMARIZATION: ["gpt-4o-mini", "claude-3-5-haiku-20241022", "gemini-2.5-flash"],
        TaskType.CLASSIFICATION: ["gpt-4o-mini", "claude-3-haiku-20240307", "llama-3.1-8b-instant"],
        TaskType.CREATIVE: ["claude-3-5-sonnet-20241022", "gpt-4o", "gemini-2.5-pro"],
        TaskType.FAST: ["llama-3.1-8b-instant", "gemini-2.5-flash", "gpt-4o-mini"],
    })


@dataclass
class CostTracker:
    """Track costs across providers and models."""

    total_cost: float = 0.0
    cost_by_provider: dict[str, float] = field(default_factory=dict)
    cost_by_model: dict[str, float] = field(default_factory=dict)
    request_count: int = 0
    total_tokens: TokenUsage = field(default_factory=TokenUsage)
    start_time: datetime = field(default_factory=datetime.utcnow)

    def track(self, response: CompletionResponse) -> None:
        """Track a completion response."""
        self.total_cost += response.cost
        self.request_count += 1
        self.total_tokens = self.total_tokens + response.usage

        # By provider
        self.cost_by_provider[response.provider] = (
            self.cost_by_provider.get(response.provider, 0.0) + response.cost
        )

        # By model
        self.cost_by_model[response.model] = (
            self.cost_by_model.get(response.model, 0.0) + response.cost
        )

    def get_summary(self) -> dict[str, Any]:
        """Get cost summary."""
        return {
            "total_cost_usd": self.total_cost,
            "request_count": self.request_count,
            "total_tokens": {
                "prompt": self.total_tokens.prompt_tokens,
                "completion": self.total_tokens.completion_tokens,
                "total": self.total_tokens.total_tokens,
            },
            "cost_by_provider": self.cost_by_provider,
            "cost_by_model": self.cost_by_model,
            "avg_cost_per_request": (
                self.total_cost / self.request_count if self.request_count > 0 else 0
            ),
            "tracking_since": self.start_time.isoformat(),
        }

    def reset(self) -> None:
        """Reset cost tracking."""
        self.total_cost = 0.0
        self.cost_by_provider = {}
        self.cost_by_model = {}
        self.request_count = 0
        self.total_tokens = TokenUsage()
        self.start_time = datetime.now(timezone.utc)


class SmartModelRouter:
    """Intelligent model router with fallback and cost tracking."""

    # Model quality rankings (subjective, based on benchmarks)
    MODEL_QUALITY_SCORES: dict[str, float] = {
        # OpenAI
        "gpt-4o": 0.95,
        "gpt-4-turbo": 0.92,
        "gpt-4": 0.90,
        "gpt-4o-mini": 0.80,
        "gpt-3.5-turbo": 0.70,
        # Anthropic
        "claude-3-opus-20240229": 0.97,
        "claude-3-5-sonnet-20241022": 0.94,
        "claude-3-sonnet-20240229": 0.88,
        "claude-3-5-haiku-20241022": 0.82,
        "claude-3-haiku-20240307": 0.75,
        # Google Gemini 2.5 & 3.0
        "gemini-2.5-pro": 0.93,
        "gemini-2.5-flash": 0.85,
        "gemini-3-flash-preview": 0.87,
        "gemini-3.1-flash-lite-preview": 0.82,
        # Google Gemini 2.0
        "gemini-2.0-flash": 0.88,
        "gemini-2.0-flash-lite": 0.80,
        # Google Gemini 1.5
        "gemini-1.5-pro": 0.91,
        "gemini-1.5-flash": 0.78,
        "gemini-pro": 0.75,
        # Groq
        "llama-3.3-70b-versatile": 0.85,
        "llama-3.2-90b-vision-preview": 0.84,
        "llama-3.1-70b-versatile": 0.84,
        "llama3-70b-8192": 0.82,
        "mixtral-8x7b-32768": 0.78,
        "llama-3.1-8b-instant": 0.65,
        "llama3-8b-8192": 0.60,
        "gemma2-9b-it": 0.62,
        # NVIDIA
        "deepseek-r1": 0.92,
        "deepseek-v3.2": 0.90,
        "step-3.5-flash": 0.88,
        "glm4.7": 0.87,
        "devstral-2-123b": 0.86,
        "llama-3.3-70b": 0.85,
        "nemotron-70b": 0.83,
    }

    # Model speed rankings (relative, based on typical latency)
    MODEL_SPEED_SCORES: dict[str, float] = {
        # Groq is fastest
        "llama-3.1-8b-instant": 0.98,
        "llama3-8b-8192": 0.97,
        "gemma2-9b-it": 0.96,
        "mixtral-8x7b-32768": 0.94,
        "llama3-70b-8192": 0.92,
        "llama-3.1-70b-versatile": 0.91,
        "llama-3.3-70b-versatile": 0.90,
        "llama-3.2-90b-vision-preview": 0.89,
        # Google Flash models
        "gemini-2.5-flash": 0.90,
        "gemini-3-flash-preview": 0.89,
        "gemini-2.0-flash": 0.88,
        "gemini-1.5-flash": 0.88,
        "gemini-2.0-flash-lite": 0.87,
        "gemini-3.1-flash-lite-preview": 0.86,
        # NVIDIA models
        "step-3.5-flash": 0.85,
        "devstral-2-123b": 0.84,
        "llama-3.3-70b": 0.83,
        "nemotron-70b": 0.82,
        "glm4.7": 0.81,
        "deepseek-v3.2": 0.80,
        "deepseek-r1": 0.79,
        # Mini models
        "gpt-4o-mini": 0.85,
        "claude-3-haiku-20240307": 0.84,
        "claude-3-5-haiku-20241022": 0.83,
        "gpt-3.5-turbo": 0.82,
        # Pro models
        "gemini-pro": 0.75,
        "gemini-2.5-pro": 0.72,
        "gemini-1.5-pro": 0.70,
        "gpt-4o": 0.68,
        "claude-3-5-sonnet-20241022": 0.65,
        "claude-3-sonnet-20240229": 0.62,
        "gpt-4-turbo": 0.55,
        "gpt-4": 0.50,
        "claude-3-opus-20240229": 0.40,
    }

    def __init__(
        self,
        openai_api_key: str | SecretStr | None = None,
        anthropic_api_key: str | SecretStr | None = None,
        google_api_key: str | SecretStr | None = None,
        groq_api_key: str | SecretStr | None = None,
        nvidia_api_key: str | SecretStr | None = None,
        config: RoutingConfig | None = None,
    ):
        self.config = config or RoutingConfig()
        self.providers: dict[str, BaseProvider] = {}
        self.cost_tracker = CostTracker()
        self._initialized = False
        self._round_robin_index = 0

        # Store API keys (handle SecretStr)
        self._api_keys = {
            "openai": self._get_key_value(openai_api_key),
            "anthropic": self._get_key_value(anthropic_api_key),
            "google": self._get_key_value(google_api_key),
            "groq": self._get_key_value(groq_api_key),
            "nvidia": self._get_key_value(nvidia_api_key),
        }

    @staticmethod
    def _get_key_value(key: str | SecretStr | None) -> str | None:
        """Extract string value from SecretStr if needed."""
        if key is None:
            return None
        if isinstance(key, SecretStr):
            return key.get_secret_value()
        return key

    async def initialize(self) -> None:
        """Initialize all configured providers."""
        if self._initialized:
            return

        # Initialize providers based on available API keys
        if self._api_keys["openai"]:
            provider = OpenAIProvider(api_key=self._api_keys["openai"])
            await provider.initialize()
            self.providers["openai"] = provider
            logger.info("Initialized OpenAI provider")

        if self._api_keys["anthropic"]:
            provider = AnthropicProvider(api_key=self._api_keys["anthropic"])
            await provider.initialize()
            self.providers["anthropic"] = provider
            logger.info("Initialized Anthropic provider")

        if self._api_keys["google"]:
            provider = GoogleProvider(api_key=self._api_keys["google"])
            await provider.initialize()
            self.providers["google"] = provider
            logger.info("Initialized Google provider")

        if self._api_keys["groq"]:
            provider = GroqProvider(api_key=self._api_keys["groq"])
            await provider.initialize()
            self.providers["groq"] = provider
            logger.info("Initialized Groq provider")

        if self._api_keys["nvidia"]:
            provider = NVIDIAProvider(api_key=self._api_keys["nvidia"])
            await provider.initialize()
            self.providers["nvidia"] = provider
            logger.info("Initialized NVIDIA provider")

        if not self.providers:
            logger.warning("No LLM providers configured")

        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown all providers."""
        for provider in self.providers.values():
            await provider.shutdown()
        self.providers.clear()
        self._initialized = False

    def list_providers(self) -> list[str]:
        """Get list of initialized provider names."""
        return list(self.providers.keys())

    def get_available_models(self) -> list[ModelInfo]:
        """Get all available models across providers."""
        models = []
        for provider in self.providers.values():
            models.extend(provider.get_models())
        return models

    def get_provider_for_model(self, model: str) -> BaseProvider | None:
        """Get the provider for a specific model."""
        for provider in self.providers.values():
            try:
                if provider.get_model_info(model):
                    return provider
            except Exception:
                # Model not found in this provider, continue to next
                pass

            # Check aliases for Anthropic and Google
            if hasattr(provider, "MODEL_ALIASES"):
                if model in provider.MODEL_ALIASES:  # type: ignore
                    return provider

        return None

    def _score_model(
        self,
        model_info: ModelInfo,
        strategy: RoutingStrategy,
    ) -> ModelScore:
        """Score a model based on routing strategy."""
        model_id = model_info.id

        quality = self.MODEL_QUALITY_SCORES.get(model_id, 0.5)
        speed = self.MODEL_SPEED_SCORES.get(model_id, 0.5)

        # Calculate cost score (inverse of cost, normalized)
        max_cost = 0.1  # $0.10 per 1K tokens as reference
        avg_cost = (model_info.cost_per_1k_input + model_info.cost_per_1k_output) / 2
        cost_score = 1.0 - min(avg_cost / max_cost, 1.0)

        # Calculate overall score based on strategy
        if strategy == RoutingStrategy.BEST_QUALITY:
            overall = quality * 0.8 + speed * 0.1 + cost_score * 0.1
        elif strategy == RoutingStrategy.BEST_SPEED:
            overall = quality * 0.1 + speed * 0.8 + cost_score * 0.1
        elif strategy == RoutingStrategy.LOWEST_COST:
            overall = quality * 0.1 + speed * 0.1 + cost_score * 0.8
        else:  # BEST_VALUE
            overall = quality * 0.4 + speed * 0.3 + cost_score * 0.3

        return ModelScore(
            model_id=model_id,
            provider=model_info.provider,
            quality_score=quality,
            speed_score=speed,
            cost_score=cost_score,
            overall_score=overall,
        )

    def route(
        self,
        task_type: TaskType = TaskType.GENERAL,
        strategy: RoutingStrategy | None = None,
        required_features: list[str] | None = None,
    ) -> tuple[str, BaseProvider] | None:
        """Route to the best model for the task.

        Args:
            task_type: Type of task to perform
            strategy: Routing strategy (uses default if not specified)
            required_features: Required model features (e.g., 'functions', 'vision')

        Returns:
            Tuple of (model_id, provider) or None if no suitable model found
        """
        if not self.providers:
            return None

        strategy = strategy or self.config.default_strategy

        # Handle round robin specially
        if strategy == RoutingStrategy.ROUND_ROBIN:
            models = self.get_available_models()
            if not models:
                return None

            # Filter by features if needed
            if required_features:
                models = self._filter_by_features(models, required_features)

            if not models:
                return None

            model = models[self._round_robin_index % len(models)]
            self._round_robin_index += 1
            provider = self.get_provider_for_model(model.id)
            return (model.id, provider) if provider else None

        # Get task preferences
        preferred_models = self.config.task_preferences.get(task_type, [])

        # Check preferred models first
        for model_id in preferred_models:
            provider = self.get_provider_for_model(model_id)
            if provider:
                model_info = provider.get_model_info(model_id)
                if model_info and self._meets_requirements(model_info, required_features):
                    return (model_id, provider)

        # Score all available models
        scored_models: list[tuple[ModelScore, BaseProvider]] = []
        for provider in self.providers.values():
            for model_info in provider.get_models():
                if self._meets_requirements(model_info, required_features):
                    score = self._score_model(model_info, strategy)
                    scored_models.append((score, provider))

        if not scored_models:
            return None

        # Sort by overall score
        scored_models.sort(key=lambda x: x[0].overall_score, reverse=True)
        best_score, best_provider = scored_models[0]

        return (best_score.model_id, best_provider)

    def _meets_requirements(
        self,
        model_info: ModelInfo,
        required_features: list[str] | None,
    ) -> bool:
        """Check if model meets required features."""
        if not required_features:
            return True

        for feature in required_features:
            if feature == "functions" and not model_info.supports_functions:
                return False
            if feature == "vision" and not model_info.supports_vision:
                return False
            if feature == "streaming" and not model_info.supports_streaming:
                return False

        return True

    def _filter_by_features(
        self,
        models: list[ModelInfo],
        required_features: list[str],
    ) -> list[ModelInfo]:
        """Filter models by required features."""
        return [m for m in models if self._meets_requirements(m, required_features)]

    async def complete(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        task_type: TaskType = TaskType.GENERAL,
        strategy: RoutingStrategy | None = None,
        required_features: list[str] | None = None,
        fallback: bool = True,
        **kwargs: Any,
    ) -> CompletionResponse:
        """Generate a completion with automatic routing and fallback.

        Args:
            messages: List of message dicts
            model: Specific model to use (overrides routing)
            task_type: Type of task for routing
            strategy: Routing strategy
            required_features: Required model features
            fallback: Enable fallback on failure
            **kwargs: Additional completion parameters

        Returns:
            CompletionResponse from the model

        Raises:
            ProviderError: If all models fail
        """
        if not self._initialized:
            await self.initialize()

        # Determine model(s) to try
        models_to_try: list[tuple[str, BaseProvider]] = []

        if model:
            # Specific model requested
            provider = self.get_provider_for_model(model)
            if provider:
                models_to_try.append((model, provider))
            else:
                raise ProviderError(f"Model {model} not found", "router")
        else:
            # Use routing
            route_result = self.route(task_type, strategy, required_features)
            if route_result:
                models_to_try.append(route_result)

        # Add fallback models
        if fallback and len(models_to_try) < self.config.max_fallback_attempts:
            # Get additional models for fallback
            preferred = self.config.task_preferences.get(task_type, [])
            for fallback_model in preferred:
                if len(models_to_try) >= self.config.max_fallback_attempts:
                    break

                provider = self.get_provider_for_model(fallback_model)
                if provider and (fallback_model, provider) not in models_to_try:
                    models_to_try.append((fallback_model, provider))

        if not models_to_try:
            raise ProviderError("No suitable models available", "router")

        # Try models in order
        last_error: Exception | None = None

        for i, (model_id, provider) in enumerate(models_to_try):
            try:
                logger.info(f"Attempting completion with {provider.PROVIDER_NAME}/{model_id}")
                response = await provider.complete(messages, model_id, **kwargs)

                # Track cost
                self.cost_tracker.track(response)

                return response

            except RateLimitError as e:
                logger.warning(f"Rate limited by {provider.PROVIDER_NAME}: {e}")
                last_error = e
                if i < len(models_to_try) - 1:
                    await asyncio.sleep(self.config.fallback_delay_seconds)

            except ProviderError as e:
                logger.warning(f"Provider error from {provider.PROVIDER_NAME}: {e}")
                last_error = e
                if i < len(models_to_try) - 1:
                    await asyncio.sleep(self.config.fallback_delay_seconds)

            except Exception as e:
                logger.error(f"Unexpected error from {provider.PROVIDER_NAME}: {e}")
                last_error = e

        # All models failed
        raise ProviderError(
            f"All models failed. Last error: {last_error}",
            "router",
        )

    def get_cost_summary(self) -> dict[str, Any]:
        """Get cost tracking summary."""
        return self.cost_tracker.get_summary()

    def reset_cost_tracking(self) -> None:
        """Reset cost tracking."""
        self.cost_tracker.reset()

    @property
    def available_providers(self) -> list[str]:
        """List of initialized provider names."""
        return list(self.providers.keys())

    def __repr__(self) -> str:
        return (
            f"SmartModelRouter(providers={list(self.providers.keys())}, "
            f"requests={self.cost_tracker.request_count}, "
            f"cost=${self.cost_tracker.total_cost:.4f})"
        )
