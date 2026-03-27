"""Settings API routes for client configuration."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/settings", tags=["settings"])

# In-memory storage for client settings (per-session)
# In production, this would be stored per-user in a database
_client_settings: dict[str, Any] = {
    "api_keys": {
        "openai": None,
        "anthropic": None,
        "google": None,
        "groq": None,
    },
    "selected_model": {
        "provider": "groq",
        "model": "gpt-oss-120b",
    },
    "plugins": [],
}


class APIKeyUpdate(BaseModel):
    """Request to update an API key."""

    provider: str = Field(..., description="Provider name: openai, anthropic, google, groq")
    api_key: str | None = Field(None, description="API key value, or null to clear")


class ModelSelection(BaseModel):
    """Request to select active model."""

    provider: str = Field(..., description="Provider name")
    model: str = Field(..., description="Model identifier")


class SettingsResponse(BaseModel):
    """Current settings state."""

    api_keys_configured: dict[str, bool]
    selected_model: dict[str, str]
    available_models: list[dict[str, Any]]
    plugins_installed: list[str]


# Available models configuration
AVAILABLE_MODELS = [
    {
        "provider": "groq",
        "model": "gpt-oss-120b",
        "name": "GPT-OSS 120B (Groq)",
        "description": "Fast open-source model via Groq",
        "default": True,
    },
    {
        "provider": "google",
        "model": "gemini-2.5-flash",
        "name": "Gemini Flash 2.5",
        "description": "Google's fast Gemini model",
        "default": False,
    },
    {
        "provider": "google",
        "model": "gemini-2.5-pro",
        "name": "Gemini Pro 2.5",
        "description": "Google's advanced Gemini model",
        "default": False,
    },
    {
        "provider": "openai",
        "model": "gpt-4o",
        "name": "GPT-4o",
        "description": "OpenAI's flagship model",
        "default": False,
    },
    {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "name": "GPT-4o Mini",
        "description": "OpenAI's efficient model",
        "default": False,
    },
    {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
        "name": "Claude 3.5 Sonnet",
        "description": "Anthropic's Claude Sonnet",
        "default": False,
    },
    {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "name": "Llama 3.3 70B",
        "description": "Meta's Llama via Groq",
        "default": False,
    },
    {
        "provider": "groq",
        "model": "mixtral-8x7b-32768",
        "name": "Mixtral 8x7B",
        "description": "Mistral's MoE model via Groq",
        "default": False,
    },
]


@router.get("/", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Get current client settings."""
    from app.config import get_settings as get_env_settings

    env_settings = get_env_settings()

    # Check which API keys are configured (either env or client)
    api_keys_configured = {
        "openai": bool(env_settings.openai_api_key or _client_settings["api_keys"]["openai"]),
        "anthropic": bool(env_settings.anthropic_api_key or _client_settings["api_keys"]["anthropic"]),
        "google": bool(env_settings.google_api_key or _client_settings["api_keys"]["google"]),
        "groq": bool(env_settings.groq_api_key or _client_settings["api_keys"]["groq"]),
    }

    return SettingsResponse(
        api_keys_configured=api_keys_configured,
        selected_model=_client_settings["selected_model"],
        available_models=AVAILABLE_MODELS,
        plugins_installed=_client_settings["plugins"],
    )


@router.post("/api-key")
async def update_api_key(update: APIKeyUpdate) -> dict[str, Any]:
    """Update a client API key."""
    if update.provider not in _client_settings["api_keys"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {update.provider}. Valid: openai, anthropic, google, groq",
        )

    _client_settings["api_keys"][update.provider] = update.api_key

    return {
        "status": "success",
        "message": f"API key for {update.provider} {'set' if update.api_key else 'cleared'}",
        "provider": update.provider,
        "configured": bool(update.api_key),
    }


@router.post("/model")
async def select_model(selection: ModelSelection) -> dict[str, Any]:
    """Select the active model."""
    # Validate model exists
    valid_model = any(
        m["provider"] == selection.provider and m["model"] == selection.model for m in AVAILABLE_MODELS
    )

    if not valid_model:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {selection.provider}/{selection.model}",
        )

    _client_settings["selected_model"] = {
        "provider": selection.provider,
        "model": selection.model,
    }

    return {
        "status": "success",
        "message": f"Model set to {selection.provider}/{selection.model}",
        "selected_model": _client_settings["selected_model"],
    }


@router.get("/api-key/required")
async def check_api_key_required() -> dict[str, Any]:
    """Check if user needs to provide API keys."""
    from app.config import get_settings as get_env_settings

    env_settings = get_env_settings()
    selected = _client_settings["selected_model"]

    # Check if selected provider has a key configured
    provider = selected["provider"]

    env_key = getattr(env_settings, f"{provider}_api_key", None)
    client_key = _client_settings["api_keys"].get(provider)

    has_key = bool(env_key or client_key)

    return {
        "required": not has_key,
        "provider": provider,
        "model": selected["model"],
        "message": None if has_key else f"Please provide an API key for {provider} to use {selected['model']}",
    }


def get_active_api_key(provider: str) -> str | None:
    """Get the active API key for a provider (client or env)."""
    from app.config import get_settings as get_env_settings

    # Client keys take precedence
    client_key = _client_settings["api_keys"].get(provider)
    if client_key:
        return client_key

    # Fall back to environment
    env_settings = get_env_settings()
    env_key = getattr(env_settings, f"{provider}_api_key", None)
    if env_key:
        return env_key.get_secret_value() if hasattr(env_key, "get_secret_value") else str(env_key)

    return None


def get_selected_model() -> dict[str, str]:
    """Get the currently selected model."""
    return _client_settings["selected_model"]
