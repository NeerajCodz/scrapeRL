"""Google AI provider implementation (Gemini models)."""

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


class GoogleProvider(BaseProvider):
    """Google AI API provider supporting Gemini models."""

    PROVIDER_NAME = "google"
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # Model definitions with pricing (per 1K tokens)
    MODELS = {
        # Gemini 2.5 Series
        "gemini-2.5-pro": ModelInfo(
            id="gemini-2.5-pro",
            name="Gemini 2.5 Pro",
            provider="google",
            context_window=2097152,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.00125,
            cost_per_1k_output=0.005,
        ),
        "gemini-2.5-flash": ModelInfo(
            id="gemini-2.5-flash",
            name="Gemini 2.5 Flash",
            provider="google",
            context_window=1048576,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.000075,
            cost_per_1k_output=0.0003,
        ),
        # Gemini 2.0 Series
        "gemini-2.0-flash": ModelInfo(
            id="gemini-2.0-flash",
            name="Gemini 2.0 Flash",
            provider="google",
            context_window=1048576,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        "gemini-2.0-flash-lite": ModelInfo(
            id="gemini-2.0-flash-lite",
            name="Gemini 2.0 Flash Lite",
            provider="google",
            context_window=524288,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        # Gemini 3.0 Series (Preview)
        "gemini-3-flash-preview": ModelInfo(
            id="gemini-3-flash-preview",
            name="Gemini 3 Flash Preview",
            provider="google",
            context_window=1048576,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        "gemini-3.1-flash-lite-preview": ModelInfo(
            id="gemini-3.1-flash-lite-preview",
            name="Gemini 3.1 Flash Lite Preview",
            provider="google",
            context_window=524288,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        # Gemini 1.5 Series (Stable)
        "gemini-1.5-pro": ModelInfo(
            id="gemini-1.5-pro",
            name="Gemini 1.5 Pro",
            provider="google",
            context_window=2097152,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.00125,
            cost_per_1k_output=0.005,
        ),
        "gemini-1.5-flash": ModelInfo(
            id="gemini-1.5-flash",
            name="Gemini 1.5 Flash",
            provider="google",
            context_window=1048576,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_input=0.000075,
            cost_per_1k_output=0.0003,
        ),
        "gemini-pro": ModelInfo(
            id="gemini-pro",
            name="Gemini Pro",
            provider="google",
            context_window=32760,
            max_output_tokens=8192,
            supports_functions=True,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_input=0.0005,
            cost_per_1k_output=0.0015,
        ),
    }

    # Aliases
    MODEL_ALIASES = {
        "gemini-flash": "gemini-2.5-flash",
        "gemini-pro-latest": "gemini-2.5-pro",
        "gemini-1.5": "gemini-1.5-pro",
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
            headers={"Content-Type": "application/json"},
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
        """Get available Google AI models."""
        return list(self.MODELS.values())

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert OpenAI-style messages to Gemini format.

        Returns:
            Tuple of (system_instruction, contents)
        """
        system_instruction: str | None = None
        contents: list[dict[str, Any]] = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_instruction = content
            elif role == "assistant":
                contents.append({
                    "role": "model",
                    "parts": [{"text": content}] if isinstance(content, str) else content,
                })
            elif role == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": content}] if isinstance(content, str) else content,
                })
            elif role == "function":
                # Function response
                contents.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.get("name", "function"),
                            "response": {"result": content},
                        }
                    }],
                })
            elif role == "tool":
                # Tool response
                contents.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.get("tool_call_id", "tool"),
                            "response": {"result": content},
                        }
                    }],
                })

        return system_instruction, contents

    def _convert_tools(
        self, tools: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]] | None:
        """Convert OpenAI-style tools to Gemini format."""
        if not tools:
            return None

        function_declarations = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                function_declarations.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {"type": "object", "properties": {}}),
                })

        return [{"functionDeclarations": function_declarations}] if function_declarations else None

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
        """Generate a completion using Google AI API."""
        await self._acquire_rate_limit()

        model = self._resolve_model(model)
        model_info = self.get_model_info(model)
        if not model_info:
            raise ModelNotFoundError(self.PROVIDER_NAME, model)

        client = await self._ensure_client()

        # Convert messages
        system_instruction, contents = self._convert_messages(messages)

        # Build request payload
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        if stop:
            payload["generationConfig"]["stopSequences"] = stop

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        # Convert tools
        gemini_tools = self._convert_tools(tools)
        if not gemini_tools and functions:
            gemini_tools = [{
                "functionDeclarations": [
                    {
                        "name": f["name"],
                        "description": f.get("description", ""),
                        "parameters": f.get("parameters", {"type": "object", "properties": {}}),
                    }
                    for f in functions
                ]
            }]

        if gemini_tools:
            payload["tools"] = gemini_tools

        start_time = time.time()

        url = f"/models/{model}:generateContent?key={self.api_key}"

        try:
            response = await self._retry_with_backoff(
                self._make_request, client, url, payload
            )
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)

        latency_ms = (time.time() - start_time) * 1000

        # Parse response
        candidates = response.get("candidates", [])
        if not candidates:
            raise ProviderError("No candidates in response", self.PROVIDER_NAME)

        candidate = candidates[0]
        content_parts = candidate.get("content", {}).get("parts", [])

        # Extract text content and function calls
        text_content = ""
        tool_calls = []

        for part in content_parts:
            if "text" in part:
                text_content += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append({
                    "id": f"call_{fc['name']}",
                    "type": "function",
                    "function": {
                        "name": fc["name"],
                        "arguments": json.dumps(fc.get("args", {})),
                    },
                })

        # Parse usage
        usage_data = response.get("usageMetadata", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("promptTokenCount", 0),
            completion_tokens=usage_data.get("candidatesTokenCount", 0),
            total_tokens=usage_data.get("totalTokenCount", 0),
        )

        cost = self.calculate_cost(model, usage)
        self._track_usage(usage, cost)

        # Map finish reason
        finish_reason_map = {
            "STOP": "stop",
            "MAX_TOKENS": "length",
            "SAFETY": "content_filter",
            "RECITATION": "content_filter",
        }
        finish_reason = finish_reason_map.get(
            candidate.get("finishReason", ""), candidate.get("finishReason")
        )

        return CompletionResponse(
            content=text_content,
            model=model,
            provider=self.PROVIDER_NAME,
            usage=usage,
            finish_reason=finish_reason,
            function_call=None,
            tool_calls=tool_calls if tool_calls else None,
            raw_response=response,
            latency_ms=latency_ms,
            cost=cost,
        )

    async def _make_request(
        self, client: httpx.AsyncClient, url: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Make the API request."""
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def _handle_http_error(self, error: httpx.HTTPStatusError) -> None:
        """Handle HTTP errors from Google AI."""
        status = error.response.status_code
        try:
            body = error.response.json()
            message = body.get("error", {}).get("message", str(error))
        except Exception:
            message = str(error)

        if status == 401 or status == 403:
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
        """Stream a completion from Google AI."""
        await self._acquire_rate_limit()

        model = self._resolve_model(model)
        model_info = self.get_model_info(model)
        if not model_info:
            raise ModelNotFoundError(self.PROVIDER_NAME, model)

        client = await self._ensure_client()

        system_instruction, contents = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"/models/{model}:streamGenerateContent?key={self.api_key}&alt=sse"

        try:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]

                        try:
                            chunk = json.loads(data)
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for part in parts:
                                    if "text" in part:
                                        yield part["text"]
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
