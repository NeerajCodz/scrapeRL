"""FastAPI application entry point with CORS and lifespan management."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import agents, episode, health, memory, plugins, tasks, tools
from app.api.routes import settings as settings_routes
from app.config import get_settings
from app.memory.manager import MemoryManager
from app.models.router import SmartModelRouter
from app.tools.registry import MCPToolRegistry
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)

# Global instances for dependency injection
_memory_manager: MemoryManager | None = None
_model_router: SmartModelRouter | None = None
_tool_registry: MCPToolRegistry | None = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    if _memory_manager is None:
        raise RuntimeError("Memory manager not initialized")
    return _memory_manager


def get_model_router() -> SmartModelRouter:
    """Get the global model router instance."""
    if _model_router is None:
        raise RuntimeError("Model router not initialized")
    return _model_router


def get_tool_registry() -> MCPToolRegistry:
    """Get the global tool registry instance."""
    if _tool_registry is None:
        raise RuntimeError("Tool registry not initialized")
    return _tool_registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan - startup and shutdown events."""
    global _memory_manager, _model_router, _tool_registry

    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Initialize components
    logger.info("Initializing memory manager...")
    _memory_manager = MemoryManager(settings)
    await _memory_manager.initialize()

    logger.info("Initializing model router...")
    _model_router = SmartModelRouter(
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
        groq_api_key=settings.groq_api_key,
        nvidia_api_key=settings.nvidia_api_key,
    )
    await _model_router.initialize()

    logger.info("Initializing tool registry...")
    _tool_registry = MCPToolRegistry()
    await _tool_registry.initialize()
    
    # Update dependency container
    from app.api import deps
    deps.container.set_memory_manager(_memory_manager)
    deps.container.set_model_router(_model_router)
    deps.container.set_tool_registry(_tool_registry)

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    if _memory_manager:
        await _memory_manager.shutdown()
    if _model_router:
        await _model_router.shutdown()
    if _tool_registry:
        await _tool_registry.shutdown()

    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        description="FastAPI-based RL environment for intelligent web scraping",
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/swagger",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Include routers
    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix, tags=["Health"])
    app.include_router(episode.router, prefix=api_prefix, tags=["Episode"])
    app.include_router(tasks.router, prefix=api_prefix, tags=["Tasks"])
    app.include_router(agents.router, prefix=api_prefix, tags=["Agents"])
    app.include_router(tools.router, prefix=api_prefix, tags=["Tools"])
    app.include_router(memory.router, prefix=api_prefix, tags=["Memory"])
    app.include_router(settings_routes.router, prefix=api_prefix, tags=["Settings"])
    app.include_router(plugins.router, prefix=api_prefix, tags=["Plugins"])
    
    # Import and include providers router
    from app.api.routes import providers
    app.include_router(providers.router, prefix=api_prefix, tags=["Providers"])

    # Serve static files (frontend build)
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
        
        @app.get("/", response_class=HTMLResponse)
        async def serve_spa():
            """Serve the main SPA index.html."""
            index_file = static_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return HTMLResponse("<h1>ScrapeRL</h1><p>Frontend not built.</p>")
        
        @app.get("/{full_path:path}")
        async def serve_spa_routes(request: Request, full_path: str):
            """Serve SPA routes - return index.html for client-side routing."""
            # Don't serve index.html for API routes
            if full_path.startswith("api/"):
                return {"detail": "Not Found"}
            
            # Check if it's a static file
            static_file = static_dir / full_path
            if static_file.exists() and static_file.is_file():
                return FileResponse(static_file)
            
            # Return index.html for SPA routing
            index_file = static_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return HTMLResponse("<h1>ScrapeRL</h1><p>Frontend not built.</p>")

    return app


# Create the application instance
app = create_app()


def run() -> None:
    """Run the application using uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
