"""Anthropic provider implementation."""

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


class AnthropicProvider(BaseProvider):
    """Anthropic API provider supporting Claude models."""

    PROVIDER_NAME = "anthropic"
    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"

    # Model definitions with pricing (per 1K tokens)
    MODELS = {
        "claude-3-opus-20240229": ModelInfo(
            id="claude-3-opus-20240229",
            name="Claude 3 Opus",
            provider="anthropic",
            context_window=200000,
            max_output_tokens=4096,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.015,
            cost_per_1k_output=0.075,
        ),
        "claude-3-sonnet-20240229": ModelInfo(
            id="claude-3-sonnet-20240229",
            name="Claude 3 Sonnet",
            provider="anthropic",
            context_window=200000,
            max_output_tokens=4096,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
        ),
        "claude-3-5-sonnet-20241022": ModelInfo(
            id="claude-3-5-sonnet-20241022",
            name="Claude 3.5 Sonnet",
            provider="anthropic",
            context_window=200000,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
        ),
        "claude-3-haiku-20240307": ModelInfo(
            id="claude-3-haiku-20240307",
            name="Claude 3 Haiku",
            provider="anthropic",
            context_window=200000,
            max_output_tokens=4096,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.00025,
            cost_per_1k_output=0.00125,
        ),
        "claude-3-5-haiku-20241022": ModelInfo(
            id="claude-3-5-haiku-20241022",
            name="Claude 3.5 Haiku",
            provider="anthropic",
            context_window=200000,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.001,
            cost_per_1k_output=0.005,
        ),
    }

    # Aliases for convenience
    MODEL_ALIASES = {
        "claude-3-opus": "claude-3-opus-20240229",
        "claude-3-sonnet": "claude-3-sonnet-20240229",
        "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3-haiku": "claude-3-haiku-20240307",
        "claude-3.5-haiku": "claude-3-5-haiku-20241022",
    }

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
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
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self.API_VERSION,
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
        """Get available Anthropic models."""
        return list(self.MODELS.values())

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert OpenAI-style messages to Anthropic format.

        Returns:
            Tuple of (system_message, converted_messages)
        """
        system_message: str | None = None
        converted: list[dict[str, Any]] = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_message = content
            elif role == "assistant":
                converted.append({"role": "assistant", "content": content})
            elif role == "user":
                converted.append({"role": "user", "content": content})
            elif role == "function":
                # Convert function result to user message
                converted.append({
                    "role": "user",
                    "content": f"Function result for {msg.get('name', 'function')}: {content}",
                })
            elif role == "tool":
                # Convert tool result
                converted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": content,
                    }],
                })

        return system_message, converted

    def _convert_tools(
        self, tools: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]] | None:
        """Convert OpenAI-style tools to Anthropic format."""
        if not tools:
            return None

        converted = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                converted.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })
        return converted if converted else None

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
        """Generate a completion using Anthropic API."""
        await self._acquire_rate_limit()

        model = self._resolve_model(model)
        model_info = self.get_model_info(model)
        if not model_info:
            raise ModelNotFoundError(self.PROVIDER_NAME, model)

        client = await self._ensure_client()

        # Convert messages
        system_message, converted_messages = self._convert_messages(messages)

        # Build request payload
        payload: dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
            "max_tokens": max_tokens or model_info.max_output_tokens,
        }

        if system_message:
            payload["system"] = system_message

        if temperature is not None:
            payload["temperature"] = temperature

        if stop:
            payload["stop_sequences"] = stop

        # Convert tools (prefer tools over functions)
        anthropic_tools = self._convert_tools(tools)
        if not anthropic_tools and functions:
            # Convert legacy functions format
            anthropic_tools = [
                {
                    "name": f["name"],
                    "description": f.get("description", ""),
                    "input_schema": f.get("parameters", {"type": "object", "properties": {}}),
                }
                for f in functions
            ]

        if anthropic_tools:
            payload["tools"] = anthropic_tools

            # Handle tool choice
            if tool_choice == "auto" or tool_choice is None:
                payload["tool_choice"] = {"type": "auto"}
            elif tool_choice == "required":
                payload["tool_choice"] = {"type": "any"}
            elif isinstance(tool_choice, dict) and "function" in tool_choice:
                payload["tool_choice"] = {"type": "tool", "name": tool_choice["function"]["name"]}

        start_time = time.time()

        try:
            response = await self._retry_with_backoff(
                self._make_request, client, payload
            )
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)

        latency_ms = (time.time() - start_time) * 1000

        # Parse response
        content_blocks = response.get("content", [])
        usage_data = response.get("usage", {})

        # Extract text content and tool uses
        text_content = ""
        tool_calls = []

        for block in content_blocks:
            if block["type"] == "text":
                text_content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block["input"]),
                    },
                })

        usage = TokenUsage(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
        )

        cost = self.calculate_cost(model, usage)
        self._track_usage(usage, cost)

        return CompletionResponse(
            content=text_content,
            model=response.get("model", model),
            provider=self.PROVIDER_NAME,
            usage=usage,
            finish_reason=response.get("stop_reason"),
            function_call=None,
            tool_calls=tool_calls if tool_calls else None,
            raw_response=response,
            latency_ms=latency_ms,
            cost=cost,
        )

    async def _make_request(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Make the API request."""
        response = await client.post("/messages", json=payload)
        response.raise_for_status()
        return response.json()

    def _handle_http_error(self, error: httpx.HTTPStatusError) -> None:
        """Handle HTTP errors from Anthropic."""
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
        """Stream a completion from Anthropic."""
        await self._acquire_rate_limit()

        model = self._resolve_model(model)
        model_info = self.get_model_info(model)
        if not model_info:
            raise ModelNotFoundError(self.PROVIDER_NAME, model)

        client = await self._ensure_client()

        system_message, converted_messages = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
            "max_tokens": max_tokens or model_info.max_output_tokens,
            "stream": True,
        }

        if system_message:
            payload["system"] = system_message

        if temperature is not None:
            payload["temperature"] = temperature

        try:
            async with client.stream("POST", "/messages", json=payload) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]

                        try:
                            event = json.loads(data)
                            event_type = event.get("type")

                            if event_type == "content_block_delta":
                                delta = event.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield delta.get("text", "")

                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
