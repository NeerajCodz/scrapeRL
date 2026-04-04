"""NVIDIA AI provider implementation via OpenAI-compatible API."""

import json
import time
from typing import Any, AsyncIterator

import httpx

from app.models.providers.base import (
    AuthenticationError,
    BaseProvider,
    CompletionResponse,
    ModelInfo,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    TokenUsage,
)


class NVIDIAProvider(BaseProvider):
    """NVIDIA AI API provider supporting reasoning and code models."""

    PROVIDER_NAME = "nvidia"
    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

    # Model definitions with configurations
    MODELS = {
        # Reasoning models
        "step-3.5-flash": ModelInfo(
            id="stepfun-ai/step-3.5-flash",
            name="Step 3.5 Flash (Reasoning)",
            provider="nvidia",
            context_window=16384,
            max_output_tokens=16384,
            supports_functions=False,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.0,  # Free tier
            cost_per_1k_output=0.0,
        ),
        "glm4.7": ModelInfo(
            id="z-ai/glm4.7",
            name="GLM 4.7 (Reasoning)",
            provider="nvidia",
            context_window=16384,
            max_output_tokens=16384,
            supports_functions=False,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        "deepseek-v3.2": ModelInfo(
            id="deepseek-ai/deepseek-v3.2",
            name="DeepSeek V3.2 (Reasoning)",
            provider="nvidia",
            context_window=8192,
            max_output_tokens=8192,
            supports_functions=False,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        "deepseek-r1": ModelInfo(
            id="deepseek-ai/deepseek-r1",
            name="DeepSeek R1 (Reasoning)",
            provider="nvidia",
            context_window=16384,
            max_output_tokens=16384,
            supports_functions=False,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        # Code models
        "devstral-2-123b": ModelInfo(
            id="mistralai/devstral-2-123b-instruct-2512",
            name="Devstral 2 123B (Code)",
            provider="nvidia",
            context_window=8192,
            max_output_tokens=8192,
            supports_functions=False,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        # General models
        "llama-3.3-70b": ModelInfo(
            id="meta/llama-3.3-70b-instruct",
            name="Llama 3.3 70B",
            provider="nvidia",
            context_window=8192,
            max_output_tokens=8192,
            supports_functions=False,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        "nemotron-70b": ModelInfo(
            id="nvidia/llama-3.1-nemotron-70b-instruct",
            name="Nemotron 70B",
            provider="nvidia",
            context_window=4096,
            max_output_tokens=4096,
            supports_functions=False,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
    }

    # Reasoning model configs
    REASONING_CONFIGS = {
        "step-3.5-flash": {
            "temperature": 1.0,
            "top_p": 0.9,
        },
        "glm4.7": {
            "temperature": 1.0,
            "top_p": 1.0,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": True, "clear_thinking": False}},
        },
        "deepseek-v3.2": {
            "temperature": 1.0,
            "top_p": 0.95,
            "extra_body": {"chat_template_kwargs": {"thinking": True}},
        },
        "deepseek-r1": {
            "temperature": 0.6,
            "top_p": 0.95,
        },
    }

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        """
        Initialize NVIDIA provider.

        Args:
            api_key: NVIDIA API key
            base_url: Base URL for NVIDIA API (defaults to integrate.api.nvidia.com)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        super().__init__(api_key, base_url or self.DEFAULT_BASE_URL, timeout, max_retries)
        self._last_request_time = 0.0

    def _get_headers(self) -> dict[str, str]:
        """Get headers for NVIDIA API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        min_interval = 0.3  # 300ms between requests
        if elapsed < min_interval:
            import asyncio
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "devstral-2-123b",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        """
        Create a chat completion using NVIDIA models.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model key (e.g., 'devstral-2-123b', 'llama-3.3-70b')
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters

        Returns:
            CompletionResponse with generated text and metadata

        Raises:
            ModelNotFoundError: If model is not supported
            AuthenticationError: If API key is invalid
            RateLimitError: If rate limit is exceeded
            ProviderError: For other API errors
        """
        # Validate model
        if model not in self.MODELS:
            raise ModelNotFoundError(f"Model {model} not found. Available: {list(self.MODELS.keys())}")

        model_info = self.MODELS[model]
        model_id = model_info.id

        # Apply rate limiting
        await self._rate_limit()

        # Build request payload
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or model_info.max_output_tokens,
        }

        # Add reasoning model configs if applicable
        if model in self.REASONING_CONFIGS:
            config = self.REASONING_CONFIGS[model]
            if "extra_body" in config:
                payload["extra_body"] = config["extra_body"]
            if "top_p" in config:
                payload["top_p"] = config["top_p"]

        # Add any additional kwargs
        payload.update(kwargs)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )

                if response.status_code == 401:
                    raise AuthenticationError("Invalid NVIDIA API key")
                elif response.status_code == 429:
                    raise RateLimitError("NVIDIA API rate limit exceeded")
                elif response.status_code >= 400:
                    error_detail = response.text
                    raise ProviderError(f"NVIDIA API error ({response.status_code}): {error_detail}")

                data = response.json()

                # Extract response
                choice = data["choices"][0]
                content = choice["message"]["content"]

                # Extract usage
                usage_data = data.get("usage", {})
                usage = TokenUsage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                )

                return CompletionResponse(
                    content=content,
                    model=model,
                    provider=self.PROVIDER_NAME,
                    usage=usage,
                    finish_reason=choice.get("finish_reason", "stop"),
                    raw_response=data,
                )

        except (AuthenticationError, RateLimitError, ProviderError, ModelNotFoundError):
            raise
        except Exception as e:
            raise ProviderError(f"NVIDIA request failed: {str(e)}") from e

    async def complete_stream(
        self,
        messages: list[dict[str, str]],
        model: str = "devstral-2-123b",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Create a streaming chat completion.

        Args:
            messages: List of message dictionaries
            model: Model key
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Content chunks as they arrive

        Raises:
            Same as complete()
        """
        if model not in self.MODELS:
            raise ModelNotFoundError(f"Model {model} not found")

        model_info = self.MODELS[model]
        model_id = model_info.id

        await self._rate_limit()

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or model_info.max_output_tokens,
            "stream": True,
        }

        if model in self.REASONING_CONFIGS:
            config = self.REASONING_CONFIGS[model]
            if "extra_body" in config:
                payload["extra_body"] = config["extra_body"]
            if "top_p" in config:
                payload["top_p"] = config["top_p"]

        payload.update(kwargs)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                ) as response:
                    if response.status_code == 401:
                        raise AuthenticationError("Invalid NVIDIA API key")
                    elif response.status_code == 429:
                        raise RateLimitError("NVIDIA API rate limit exceeded")
                    elif response.status_code >= 400:
                        error_detail = await response.aread()
                        raise ProviderError(f"NVIDIA API error: {error_detail.decode()}")

                    async for line in response.aiter_lines():
                        if not line.strip() or not line.startswith("data: "):
                            continue

                        data_str = line[6:]  # Remove 'data: ' prefix
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

        except (AuthenticationError, RateLimitError, ProviderError, ModelNotFoundError):
            raise
        except Exception as e:
            raise ProviderError(f"NVIDIA streaming failed: {str(e)}") from e

    def list_models(self) -> list[ModelInfo]:
        """List all available NVIDIA models."""
        return list(self.MODELS.values())

    def get_model_info(self, model: str) -> ModelInfo:
        """Get information about a specific model."""
        if model not in self.MODELS:
            raise ModelNotFoundError(f"Model {model} not found")
        return self.MODELS[model]
