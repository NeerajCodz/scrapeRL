"""Base provider abstract class and common types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable
import asyncio
import time


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(self, message: str, provider: str, status_code: int | None = None):
        self.message = message
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")


class RateLimitError(ProviderError):
    """Rate limit exceeded error."""

    def __init__(
        self,
        provider: str,
        retry_after: float | None = None,
        message: str = "Rate limit exceeded",
    ):
        self.retry_after = retry_after
        super().__init__(message, provider, status_code=429)


class ModelNotFoundError(ProviderError):
    """Model not found or not available error."""

    def __init__(self, provider: str, model: str):
        super().__init__(f"Model '{model}' not found", provider, status_code=404)


class AuthenticationError(ProviderError):
    """Authentication failed error."""

    def __init__(self, provider: str, message: str = "Authentication failed"):
        super().__init__(message, provider, status_code=401)


@dataclass
class TokenUsage:
    """Token usage tracking."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class CompletionResponse:
    """Standardized completion response across providers."""

    content: str
    model: str
    provider: str
    usage: TokenUsage
    finish_reason: str | None = None
    function_call: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    raw_response: dict[str, Any] | None = None
    latency_ms: float = 0.0
    cost: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
            },
            "finish_reason": self.finish_reason,
            "function_call": self.function_call,
            "tool_calls": self.tool_calls,
            "latency_ms": self.latency_ms,
            "cost": self.cost,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ModelInfo:
    """Model information and capabilities."""

    id: str
    name: str
    provider: str
    context_window: int
    max_output_tokens: int
    supports_functions: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0

    @property
    def cost_per_million_input(self) -> float:
        """Cost per million input tokens."""
        return self.cost_per_1k_input * 1000

    @property
    def cost_per_million_output(self) -> float:
        """Cost per million output tokens."""
        return self.cost_per_1k_output * 1000


class TaskType(str, Enum):
    """Types of tasks for model routing."""

    GENERAL = "general"
    CODE = "code"
    REASONING = "reasoning"
    EXTRACTION = "extraction"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"
    CREATIVE = "creative"
    FAST = "fast"


@dataclass
class RateLimitState:
    """Rate limiter state."""

    tokens: float
    last_update: float
    max_tokens: float
    refill_rate: float  # tokens per second


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    PROVIDER_NAME: str = "base"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        rate_limit_rpm: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries

        # Rate limiting (token bucket)
        self._rate_limit = RateLimitState(
            tokens=rate_limit_rpm,
            last_update=time.time(),
            max_tokens=rate_limit_rpm,
            refill_rate=rate_limit_rpm / 60.0,
        )
        self._rate_limit_lock = asyncio.Lock()

        # Usage tracking
        self._total_usage = TokenUsage()
        self._total_cost: float = 0.0
        self._request_count: int = 0

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        functions: list[dict[str, Any]] | None = None,
        function_call: str | dict[str, str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        """Generate a completion from the model.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            functions: Function definitions for function calling
            function_call: Function call mode or specific function
            tools: Tool definitions (newer format)
            tool_choice: Tool choice mode or specific tool
            stop: Stop sequences
            **kwargs: Additional provider-specific parameters

        Returns:
            CompletionResponse with generated content and metadata
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion from the model.

        Args:
            messages: List of message dicts
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Content chunks as they arrive
        """
        ...

    @abstractmethod
    def get_models(self) -> list[ModelInfo]:
        """Get list of available models from this provider.

        Returns:
            List of ModelInfo objects
        """
        ...

    def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get info for a specific model.

        Args:
            model_id: Model identifier

        Returns:
            ModelInfo or None if not found
        """
        for model in self.get_models():
            if model.id == model_id:
                return model
        return None

    def calculate_cost(self, model: str, usage: TokenUsage) -> float:
        """Calculate cost for a completion.

        Args:
            model: Model identifier
            usage: Token usage

        Returns:
            Cost in USD
        """
        model_info = self.get_model_info(model)
        if not model_info:
            return 0.0

        input_cost = (usage.prompt_tokens / 1000) * model_info.cost_per_1k_input
        output_cost = (usage.completion_tokens / 1000) * model_info.cost_per_1k_output
        return input_cost + output_cost

    async def _acquire_rate_limit(self) -> None:
        """Acquire a token from the rate limiter."""
        async with self._rate_limit_lock:
            now = time.time()
            elapsed = now - self._rate_limit.last_update

            # Refill tokens
            self._rate_limit.tokens = min(
                self._rate_limit.max_tokens,
                self._rate_limit.tokens + elapsed * self._rate_limit.refill_rate,
            )
            self._rate_limit.last_update = now

            if self._rate_limit.tokens < 1:
                # Calculate wait time
                wait_time = (1 - self._rate_limit.tokens) / self._rate_limit.refill_rate
                await asyncio.sleep(wait_time)
                self._rate_limit.tokens = 0
            else:
                self._rate_limit.tokens -= 1

    def _track_usage(self, usage: TokenUsage, cost: float) -> None:
        """Track usage and cost."""
        self._total_usage = self._total_usage + usage
        self._total_cost += cost
        self._request_count += 1

    @property
    def total_usage(self) -> TokenUsage:
        """Get total token usage."""
        return self._total_usage

    @property
    def total_cost(self) -> float:
        """Get total cost in USD."""
        return self._total_cost

    @property
    def request_count(self) -> int:
        """Get total request count."""
        return self._request_count

    def reset_tracking(self) -> None:
        """Reset usage tracking."""
        self._total_usage = TokenUsage()
        self._total_cost = 0.0
        self._request_count = 0

    async def _retry_with_backoff(
        self,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Retry a function with exponential backoff.

        Args:
            func: Async function to retry
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except RateLimitError as e:
                last_exception = e
                wait_time = e.retry_after or (2**attempt)
                await asyncio.sleep(wait_time)
            except ProviderError as e:
                # Don't retry auth or not found errors
                if e.status_code in (401, 403, 404):
                    raise
                last_exception = e
                await asyncio.sleep(2**attempt)

        if last_exception:
            raise last_exception

    async def initialize(self) -> None:
        """Initialize the provider (optional setup)."""
        pass

    async def shutdown(self) -> None:
        """Cleanup resources."""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(requests={self._request_count}, cost=${self._total_cost:.4f})"
