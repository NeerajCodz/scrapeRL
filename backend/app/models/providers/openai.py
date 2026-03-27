"""OpenAI provider implementation."""

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


class OpenAIProvider(BaseProvider):
    """OpenAI API provider supporting GPT models."""

    PROVIDER_NAME = "openai"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    # Model definitions with pricing (per 1K tokens)
    MODELS = {
        "gpt-4o": ModelInfo(
            id="gpt-4o",
            name="GPT-4o",
            provider="openai",
            context_window=128000,
            max_output_tokens=16384,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
        ),
        "gpt-4o-mini": ModelInfo(
            id="gpt-4o-mini",
            name="GPT-4o Mini",
            provider="openai",
            context_window=128000,
            max_output_tokens=16384,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
        ),
        "gpt-4-turbo": ModelInfo(
            id="gpt-4-turbo",
            name="GPT-4 Turbo",
            provider="openai",
            context_window=128000,
            max_output_tokens=4096,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03,
        ),
        "gpt-4": ModelInfo(
            id="gpt-4",
            name="GPT-4",
            provider="openai",
            context_window=8192,
            max_output_tokens=4096,
            supports_functions=True,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.03,
            cost_per_1k_output=0.06,
        ),
        "gpt-3.5-turbo": ModelInfo(
            id="gpt-3.5-turbo",
            name="GPT-3.5 Turbo",
            provider="openai",
            context_window=16385,
            max_output_tokens=4096,
            supports_functions=True,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.0005,
            cost_per_1k_output=0.0015,
        ),
    }

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        organization: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        rate_limit_rpm: int = 60,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url or self.DEFAULT_BASE_URL,
            timeout=timeout,
            max_retries=max_retries,
            rate_limit_rpm=rate_limit_rpm,
        )
        self.organization = organization
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
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

    def get_models(self) -> list[ModelInfo]:
        """Get available OpenAI models."""
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
        """Generate a completion using OpenAI API."""
        await self._acquire_rate_limit()

        model_info = self.get_model_info(model)
        if not model_info:
            raise ModelNotFoundError(self.PROVIDER_NAME, model)

        client = await self._ensure_client()

        # Build request payload
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop"] = stop

        # Function calling (legacy format)
        if functions and model_info.supports_functions:
            payload["functions"] = functions
            if function_call:
                payload["function_call"] = function_call

        # Tools (newer format)
        if tools and model_info.supports_functions:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        # Additional kwargs
        for key in ["top_p", "presence_penalty", "frequency_penalty", "logit_bias", "user"]:
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

        # Parse response
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

        # Extract function call / tool calls
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
        """Handle HTTP errors from OpenAI."""
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
        """Stream a completion from OpenAI."""
        await self._acquire_rate_limit()

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

    async def create_embedding(
        self,
        text: str | list[str],
        model: str = "text-embedding-3-small",
    ) -> list[list[float]]:
        """Create embeddings for text.

        Args:
            text: Text or list of texts to embed
            model: Embedding model to use

        Returns:
            List of embedding vectors
        """
        client = await self._ensure_client()

        payload = {
            "model": model,
            "input": text if isinstance(text, list) else [text],
        }

        response = await client.post("/embeddings", json=payload)
        response.raise_for_status()

        data = response.json()
        return [item["embedding"] for item in data["data"]]
