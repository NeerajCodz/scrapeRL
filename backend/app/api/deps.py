"""Dependency injection utilities for API routes."""

from typing import Annotated, Generator

from fastapi import Depends, HTTPException, status

from app.config import Settings, get_settings
from app.core.env import WebScraperEnv
from app.memory.manager import MemoryManager
from app.models.router import SmartModelRouter
from app.tools.registry import MCPToolRegistry


# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]


# Store for active environments
_active_environments: dict[str, WebScraperEnv] = {}


def get_environment(episode_id: str) -> WebScraperEnv:
    """Get an active environment by episode ID."""
    if episode_id not in _active_environments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode {episode_id} not found",
        )
    return _active_environments[episode_id]


def create_environment(episode_id: str, settings: Settings) -> WebScraperEnv:
    """Create a new environment for an episode."""
    if episode_id in _active_environments:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Episode {episode_id} already exists",
        )
    env = WebScraperEnv(episode_id=episode_id, settings=settings)
    _active_environments[episode_id] = env
    return env


def remove_environment(episode_id: str) -> bool:
    """Remove an environment from active storage."""
    if episode_id in _active_environments:
        del _active_environments[episode_id]
        return True
    return False


def list_environments() -> list[str]:
    """List all active episode IDs."""
    return list(_active_environments.keys())


class DependencyContainer:
    """Container for dependency injection across the application."""

    def __init__(self) -> None:
        self._memory_manager: MemoryManager | None = None
        self._model_router: SmartModelRouter | None = None
        self._tool_registry: MCPToolRegistry | None = None

    def set_memory_manager(self, manager: MemoryManager) -> None:
        """Set the memory manager instance."""
        self._memory_manager = manager

    def set_model_router(self, router: SmartModelRouter) -> None:
        """Set the model router instance."""
        self._model_router = router

    def set_tool_registry(self, registry: MCPToolRegistry) -> None:
        """Set the tool registry instance."""
        self._tool_registry = registry

    def get_memory_manager(self) -> MemoryManager:
        """Get the memory manager instance."""
        if self._memory_manager is None:
            raise RuntimeError("Memory manager not initialized")
        return self._memory_manager

    def get_model_router(self) -> SmartModelRouter:
        """Get the model router instance."""
        if self._model_router is None:
            raise RuntimeError("Model router not initialized")
        return self._model_router

    def get_tool_registry(self) -> MCPToolRegistry:
        """Get the tool registry instance."""
        if self._tool_registry is None:
            raise RuntimeError("Tool registry not initialized")
        return self._tool_registry


# Global container instance
container = DependencyContainer()


def get_memory_manager() -> MemoryManager:
    """Dependency for memory manager."""
    return container.get_memory_manager()


def get_model_router() -> SmartModelRouter:
    """Dependency for model router."""
    return container.get_model_router()


def get_tool_registry() -> MCPToolRegistry:
    """Dependency for tool registry."""
    return container.get_tool_registry()


# Type aliases for dependency injection
MemoryManagerDep = Annotated[MemoryManager, Depends(get_memory_manager)]
ModelRouterDep = Annotated[SmartModelRouter, Depends(get_model_router)]
ToolRegistryDep = Annotated[MCPToolRegistry, Depends(get_tool_registry)]
