"""Provider management API routes."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_model_router
from app.models.router import SmartModelRouter

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderInfo(BaseModel):
    """Provider information."""
    
    id: str
    name: str
    available: bool
    models_count: int
    features: list[str]


class ModelInfo(BaseModel):
    """Model information."""
    
    id: str
    name: str
    provider: str
    context_window: int
    max_output_tokens: int
    supports_functions: bool
    supports_vision: bool
    supports_streaming: bool
    cost_per_1k_input: float
    cost_per_1k_output: float


@router.get("")
@router.get("/")
async def list_providers(router: SmartModelRouter = Depends(get_model_router)) -> dict[str, Any]:
    """
    List all initialized AI providers.
    
    Returns:
        Dictionary with providers list and summary statistics
    """
    providers_list = []
    
    for provider_name in router.list_providers():
        provider_obj = router.providers.get(provider_name)
        if provider_obj:
            models = provider_obj.list_models()
            features = []
            
            # Check provider capabilities
            if any(m.supports_functions for m in models):
                features.append("functions")
            if any(m.supports_vision for m in models):
                features.append("vision")
            if any(m.supports_streaming for m in models):
                features.append("streaming")
            
            providers_list.append(ProviderInfo(
                id=provider_name,
                name=provider_obj.PROVIDER_NAME.title(),
                available=True,
                models_count=len(models),
                features=features,
            ))
    
    return {
        "providers": [p.model_dump() for p in providers_list],
        "count": len(providers_list),
        "available_models_count": sum(p.models_count for p in providers_list),
    }


@router.get("/{provider_name}")
async def get_provider_details(
    provider_name: str,
    router: SmartModelRouter = Depends(get_model_router),
) -> dict[str, Any]:
    """
    Get detailed information about a specific provider.
    
    Args:
        provider_name: Provider identifier (openai, google, anthropic, groq, nvidia)
        
    Returns:
        Provider details including all available models
    """
    provider_obj = router.providers.get(provider_name)
    if not provider_obj:
        return {
            "error": f"Provider '{provider_name}' not initialized",
            "available_providers": router.list_providers(),
        }
    
    models = provider_obj.list_models()
    
    return {
        "id": provider_name,
        "name": provider_obj.PROVIDER_NAME.title(),
        "available": True,
        "models": [ModelInfo(
            id=m.id,
            name=m.name,
            provider=m.provider,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            supports_functions=m.supports_functions,
            supports_vision=m.supports_vision,
            supports_streaming=m.supports_streaming,
            cost_per_1k_input=m.cost_per_1k_input,
            cost_per_1k_output=m.cost_per_1k_output,
        ).model_dump() for m in models],
        "models_count": len(models),
    }


@router.get("/models/all")
async def list_all_models(
    router: SmartModelRouter = Depends(get_model_router),
) -> dict[str, Any]:
    """
    List all available models across all providers.
    
    Returns:
        List of all models with their details
    """
    all_models = router.get_available_models()
    
    return {
        "models": [ModelInfo(
            id=m.id,
            name=m.name,
            provider=m.provider,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            supports_functions=m.supports_functions,
            supports_vision=m.supports_vision,
            supports_streaming=m.supports_streaming,
            cost_per_1k_input=m.cost_per_1k_input,
            cost_per_1k_output=m.cost_per_1k_output,
        ).model_dump() for m in all_models],
        "count": len(all_models),
        "by_provider": {
            provider: len([m for m in all_models if m.provider == provider])
            for provider in router.list_providers()
        },
    }


@router.get("/costs/summary")
async def get_cost_summary(
    router: SmartModelRouter = Depends(get_model_router),
) -> dict[str, Any]:
    """
    Get cost tracking summary.
    
    Returns:
        Cost statistics across all providers and models
    """
    return router.get_cost_summary()


@router.post("/costs/reset")
async def reset_cost_tracking(
    router: SmartModelRouter = Depends(get_model_router),
) -> dict[str, str]:
    """
    Reset cost tracking counters.
    
    Returns:
        Confirmation message
    """
    router.reset_cost_tracking()
    return {"status": "success", "message": "Cost tracking reset"}
