"""Groq provider implementation (fast inference)."""

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


class GroqProvider(BaseProvider):
    """Groq API provider for fast LLM inference."""

    PROVIDER_NAME = "groq"
    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"

    # Model definitions with pricing (per 1K tokens)
    MODELS = {
        "llama-3.3-70b-versatile": ModelInfo(
            id="llama-3.3-70b-versatile",
            name="Llama 3.3 70B Versatile",
            provider="groq",
            context_window=128000,
            max_output_tokens=32768,
            supports_functions=True,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.00059,
            cost_per_1k_output=0.00079,
        ),
        "llama-3.1-70b-versatile": ModelInfo(
            id="llama-3.1-70b-versatile",
            name="Llama 3.1 70B Versatile",
            provider="groq",
            context_window=128000,
            max_output_tokens=32768,
            supports_functions=True,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.00059,
            cost_per_1k_output=0.00079,
        ),
        "llama-3.1-8b-instant": ModelInfo(
            id="llama-3.1-8b-instant",
            name="Llama 3.1 8B Instant",
            provider="groq",
            context_window=128000,
            max_output_tokens=8000,
            supports_functions=True,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.00005,
            cost_per_1k_output=0.00008,
        ),
        "llama3-70b-8192": ModelInfo(
            id="llama3-70b-8192",
            name="Llama 3 70B",
            provider="groq",
            context_window=8192,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.00059,
            cost_per_1k_output=0.00079,
        ),
        "llama3-8b-8192": ModelInfo(
            id="llama3-8b-8192",
            name="Llama 3 8B",
            provider="groq",
            context_window=8192,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.00005,
            cost_per_1k_output=0.00008,
        ),
        "mixtral-8x7b-32768": ModelInfo(
            id="mixtral-8x7b-32768",
            name="Mixtral 8x7B",
            provider="groq",
            context_window=32768,
            max_output_tokens=32768,
            supports_functions=True,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.00024,
            cost_per_1k_output=0.00024,
        ),
        "gemma2-9b-it": ModelInfo(
            id="gemma2-9b-it",
            name="Gemma 2 9B IT",
            provider="groq",
            context_window=8192,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.00020,
            cost_per_1k_output=0.00020,
        ),
    }

    # Aliases for convenience
    MODEL_ALIASES = {
        "llama3": "llama3-70b-8192",
        "llama3-70b": "llama3-70b-8192",
        "llama3-8b": "llama3-8b-8192",
        "llama-3.1": "llama-3.1-70b-versatile",
        "llama-3.3": "llama-3.3-70b-versatile",
        "mixtral": "mixtral-8x7b-32768",
        "gemma2": "gemma2-9b-it",
    }

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        rate_limit_rpm: int = 30,  # Groq has stricter limits
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url or self.DEFAULT_BASE_URL,
            timeout=timeout,
            max_retries=max_retries,
            rate_limit_rpm=rate_limit_rpm,
        )
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure client is initialized."""
        if not self._client:
            await self.initialize()
        return self._client  # type: ignore

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self.MODEL_ALIASES.get(model, model)

    def get_models(self) -> list[ModelInfo]:
        """Get available Groq models."""
        return list(self.MODELS.values())

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
        """Generate a completion using Groq API (OpenAI-compatible)."""
        await self._acquire_rate_limit()

        model = self._resolve_model(model)
        model_info = self.get_model_info(model)
        if not model_info:
            raise ModelNotFoundError(self.PROVIDER_NAME, model)

        client = await self._ensure_client()

        # Build request payload (OpenAI-compatible format)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop"] = stop

        # Function calling
        if functions and model_info.supports_functions:
            payload["functions"] = functions
            if function_call:
                payload["function_call"] = function_call

        # Tools (newer format)
        if tools and model_info.supports_functions:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        # Additional params
        for key in ["top_p", "presence_penalty", "frequency_penalty"]:
            if key in kwargs:
                payload[key] = kwargs[key]

        start_time = time.time()

        try:
            response = await self._retry_with_backoff(
                self._make_request, client, payload
            )
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)

        latency_ms = (time.time() - start_time) * 1000

        # Parse response (OpenAI-compatible)
        choice = response["choices"][0]
        message = choice["message"]
        usage_data = response.get("usage", {})

        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        cost = self.calculate_cost(model, usage)
        self._track_usage(usage, cost)

        # Extract function/tool calls
        func_call = message.get("function_call")
        tool_calls_raw = message.get("tool_calls")

        tool_calls = None
        if tool_calls_raw:
            tool_calls = [
                {
                    "id": tc["id"],
                    "type": tc["type"],
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                for tc in tool_calls_raw
            ]

        return CompletionResponse(
            content=message.get("content") or "",
            model=response.get("model", model),
            provider=self.PROVIDER_NAME,
            usage=usage,
            finish_reason=choice.get("finish_reason"),
            function_call=func_call,
            tool_calls=tool_calls,
            raw_response=response,
            latency_ms=latency_ms,
            cost=cost,
        )

    async def _make_request(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Make the API request."""
        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()

    def _handle_http_error(self, error: httpx.HTTPStatusError) -> None:
        """Handle HTTP errors from Groq."""
        status = error.response.status_code
        try:
            body = error.response.json()
            message = body.get("error", {}).get("message", str(error))
        except Exception:
            message = str(error)

        if status == 401:
            raise AuthenticationError(self.PROVIDER_NAME, message)
        elif status == 429:
            retry_after = error.response.headers.get("retry-after")
            raise RateLimitError(
                self.PROVIDER_NAME,
                retry_after=float(retry_after) if retry_after else None,
                message=message,
            )
        elif status == 404:
            raise ModelNotFoundError(self.PROVIDER_NAME, "unknown")
        else:
            raise ProviderError(message, self.PROVIDER_NAME, status)

    async def stream(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion from Groq."""
        await self._acquire_rate_limit()

        model = self._resolve_model(model)
        model_info = self.get_model_info(model)
        if not model_info:
            raise ModelNotFoundError(self.PROVIDER_NAME, model)

        client = await self._ensure_client()

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
