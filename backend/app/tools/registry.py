"""MCP Tool Registry for dynamic tool discovery and management."""

import asyncio
from typing import Any, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum

from app.utils.logging import get_logger

logger = get_logger(__name__)


class ToolStatus(Enum):
    """Status of a registered tool."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    INITIALIZING = "initializing"
    SHUTDOWN = "shutdown"


@dataclass
class ToolDefinition:
    """Definition of a registered tool."""

    name: str
    description: str
    handler: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)
    status: ToolStatus = ToolStatus.UNKNOWN
    metadata: dict[str, Any] = field(default_factory=dict)


class MCPToolRegistry:
    """
    Registry for MCP tools with dynamic discovery and execution.

    Manages tool lifecycle including registration, health checks,
    and execution routing.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._initialized: bool = False
        self._health_check_interval: float = 30.0
        self._health_check_task: Optional[asyncio.Task[None]] = None

    async def initialize(self) -> None:
        """Initialize the registry and start health monitoring."""
        if self._initialized:
            logger.warning("Registry already initialized")
            return

        logger.info("Initializing MCP Tool Registry")

        # Start health check background task
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._initialized = True

        logger.info("MCP Tool Registry initialized")

    async def shutdown(self) -> None:
        """Shutdown the registry and cleanup resources."""
        logger.info("Shutting down MCP Tool Registry")

        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Mark all tools as shutdown
        for tool in self._tools.values():
            tool.status = ToolStatus.SHUTDOWN

        self._initialized = False
        logger.info("MCP Tool Registry shutdown complete")

    def register(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str = "",
        parameters: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ToolDefinition:
        """
        Register a new tool with the registry.

        Args:
            name: Unique tool name
            handler: Callable that implements the tool
            description: Human-readable description
            parameters: JSON schema for tool parameters
            metadata: Additional tool metadata

        Returns:
            The registered ToolDefinition

        Raises:
            ValueError: If a tool with the same name already exists
        """
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")

        tool = ToolDefinition(
            name=name,
            description=description,
            handler=handler,
            parameters=parameters or {},
            status=ToolStatus.INITIALIZING,
            metadata=metadata or {},
        )

        self._tools[name] = tool
        logger.info(f"Registered tool: {name}")

        return tool

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool from the registry.

        Args:
            name: Tool name to unregister

        Returns:
            True if tool was removed, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[ToolDefinition]:
        """
        Get a tool definition by name.

        Args:
            name: Tool name to retrieve

        Returns:
            ToolDefinition if found, None otherwise
        """
        return self._tools.get(name)

    def list_tools(
        self,
        include_unhealthy: bool = False,
    ) -> list[ToolDefinition]:
        """
        List all registered tools.

        Args:
            include_unhealthy: Include tools with unhealthy status

        Returns:
            List of tool definitions
        """
        tools = list(self._tools.values())

        if not include_unhealthy:
            tools = [
                t for t in tools
                if t.status not in (ToolStatus.UNHEALTHY, ToolStatus.SHUTDOWN)
            ]

        return tools

    async def execute(
        self,
        name: str,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a tool by name with the given parameters.

        Args:
            name: Tool name to execute
            **kwargs: Tool parameters

        Returns:
            Tool execution result

        Raises:
            KeyError: If tool is not found
            RuntimeError: If tool is not healthy
        """
        tool = self.get(name)

        if tool is None:
            raise KeyError(f"Tool '{name}' not found")

        if tool.status == ToolStatus.UNHEALTHY:
            raise RuntimeError(f"Tool '{name}' is unhealthy")

        if tool.status == ToolStatus.SHUTDOWN:
            raise RuntimeError(f"Tool '{name}' has been shut down")

        logger.debug(f"Executing tool: {name} with params: {kwargs}")

        try:
            # Handle both sync and async handlers
            if asyncio.iscoroutinefunction(tool.handler):
                result = await tool.handler(**kwargs)
            else:
                result = tool.handler(**kwargs)

            return result

        except Exception as e:
            logger.error(f"Tool execution failed: {name} - {e}")
            raise

    async def health_check(self, name: str) -> ToolStatus:
        """
        Check the health of a specific tool.

        Args:
            name: Tool name to check

        Returns:
            Current tool status
        """
        tool = self.get(name)
        if tool is None:
            return ToolStatus.UNKNOWN

        try:
            # Try to call a health check method if available
            handler = tool.handler
            if hasattr(handler, "health_check"):
                health_fn = getattr(handler, "health_check")
                if asyncio.iscoroutinefunction(health_fn):
                    await health_fn()
                else:
                    health_fn()

            tool.status = ToolStatus.HEALTHY
        except Exception as e:
            logger.warning(f"Health check failed for {name}: {e}")
            tool.status = ToolStatus.UNHEALTHY

        return tool.status

    async def health_check_all(self) -> dict[str, ToolStatus]:
        """
        Check health of all registered tools.

        Returns:
            Dictionary mapping tool names to their status
        """
        results: dict[str, ToolStatus] = {}

        for name in self._tools:
            results[name] = await self.health_check(name)

        return results

    async def _health_check_loop(self) -> None:
        """Background task for periodic health checks."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self.health_check_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    def get_tool_schema(self, name: str) -> Optional[dict[str, Any]]:
        """
        Get the JSON schema for a tool's parameters.

        Args:
            name: Tool name

        Returns:
            Parameter schema dict or None if not found
        """
        tool = self.get(name)
        if tool is None:
            return None

        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }

    def list_schemas(self) -> list[dict[str, Any]]:
        """
        Get schemas for all registered tools.

        Returns:
            List of tool schema dictionaries
        """
        schemas = []
        for name in self._tools:
            schema = self.get_tool_schema(name)
            if schema:
                schemas.append(schema)
        return schemas

    @property
    def is_initialized(self) -> bool:
        """Check if the registry has been initialized."""
        return self._initialized

    @property
    def tool_count(self) -> int:
        """Get the number of registered tools."""
        return len(self._tools)
