"""Plugin management API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/plugins", tags=["plugins"])

# Plugin registry - available plugins
PLUGIN_REGISTRY = {
    # API Providers
    "apis": [
        {
            "id": "openai-api",
            "name": "OpenAI API",
            "category": "apis",
            "description": "GPT-4, GPT-4o, and embedding models",
            "version": "1.0.0",
            "size": "50KB",
            "installed": False,
            "requires_key": True,
        },
        {
            "id": "anthropic-api",
            "name": "Anthropic API",
            "category": "apis",
            "description": "Claude 3.5 Sonnet and Opus models",
            "version": "1.0.0",
            "size": "45KB",
            "installed": False,
            "requires_key": True,
        },
        {
            "id": "google-api",
            "name": "Google Gemini API",
            "category": "apis",
            "description": "Gemini Pro and Flash models",
            "version": "1.0.0",
            "size": "48KB",
            "installed": True,  # Pre-installed
            "requires_key": True,
        },
        {
            "id": "groq-api",
            "name": "Groq API",
            "category": "apis",
            "description": "Fast inference for open models",
            "version": "1.0.0",
            "size": "40KB",
            "installed": True,  # Pre-installed
            "requires_key": True,
        },
        {
            "id": "ollama-api",
            "name": "Ollama (Local)",
            "category": "apis",
            "description": "Run models locally with Ollama",
            "version": "1.0.0",
            "size": "35KB",
            "installed": False,
            "requires_key": False,
        },
    ],
    # MCP Tools
    "mcps": [
        {
            "id": "mcp-browser",
            "name": "Browser Tools",
            "category": "mcps",
            "description": "Playwright-based browser automation",
            "version": "1.0.0",
            "size": "120KB",
            "installed": True,
            "requires_key": False,
        },
        {
            "id": "mcp-search",
            "name": "Search Tools",
            "category": "mcps",
            "description": "Google, Bing, DuckDuckGo search",
            "version": "1.0.0",
            "size": "80KB",
            "installed": True,
            "requires_key": False,
        },
        {
            "id": "mcp-html",
            "name": "HTML Processing",
            "category": "mcps",
            "description": "Parse, extract, and transform HTML",
            "version": "1.0.0",
            "size": "60KB",
            "installed": True,
            "requires_key": False,
        },
        {
            "id": "mcp-screenshot",
            "name": "Screenshot Tools",
            "category": "mcps",
            "description": "Capture and analyze page screenshots",
            "version": "1.0.0",
            "size": "90KB",
            "installed": False,
            "requires_key": False,
        },
        {
            "id": "mcp-pdf",
            "name": "PDF Tools",
            "category": "mcps",
            "description": "Extract data from PDF documents",
            "version": "1.0.0",
            "size": "150KB",
            "installed": False,
            "requires_key": False,
        },
        {
            "id": "mcp-database",
            "name": "Database Tools",
            "category": "mcps",
            "description": "Connect to SQL/NoSQL databases",
            "version": "1.0.0",
            "size": "100KB",
            "installed": False,
            "requires_key": False,
        },
    ],
    # Skills/Agents
    "skills": [
        {
            "id": "skill-planner",
            "name": "Planner Agent",
            "category": "skills",
            "description": "Strategic task planning",
            "version": "1.0.0",
            "size": "75KB",
            "installed": True,
            "requires_key": False,
        },
        {
            "id": "skill-navigator",
            "name": "Navigator Agent",
            "category": "skills",
            "description": "Web navigation and interaction",
            "version": "1.0.0",
            "size": "85KB",
            "installed": True,
            "requires_key": False,
        },
        {
            "id": "skill-extractor",
            "name": "Extractor Agent",
            "category": "skills",
            "description": "Data extraction and parsing",
            "version": "1.0.0",
            "size": "95KB",
            "installed": True,
            "requires_key": False,
        },
        {
            "id": "skill-verifier",
            "name": "Verifier Agent",
            "category": "skills",
            "description": "Data validation and verification",
            "version": "1.0.0",
            "size": "70KB",
            "installed": True,
            "requires_key": False,
        },
        {
            "id": "skill-captcha",
            "name": "Captcha Solver",
            "category": "skills",
            "description": "Solve CAPTCHAs and challenges",
            "version": "1.0.0",
            "size": "200KB",
            "installed": False,
            "requires_key": True,
        },
        {
            "id": "skill-stealth",
            "name": "Stealth Mode",
            "category": "skills",
            "description": "Anti-detection and fingerprint masking",
            "version": "1.0.0",
            "size": "180KB",
            "installed": False,
            "requires_key": False,
        },
    ],
    # Data Processors
    "processors": [
        {
            "id": "proc-json",
            "name": "JSON Processor",
            "category": "processors",
            "description": "Parse and transform JSON data",
            "version": "1.0.0",
            "size": "25KB",
            "installed": True,
            "requires_key": False,
        },
        {
            "id": "proc-csv",
            "name": "CSV Processor",
            "category": "processors",
            "description": "Parse and export CSV files",
            "version": "1.0.0",
            "size": "30KB",
            "installed": True,
            "requires_key": False,
        },
        {
            "id": "proc-excel",
            "name": "Excel Processor",
            "category": "processors",
            "description": "Read/write Excel files",
            "version": "1.0.0",
            "size": "500KB",
            "installed": False,
            "requires_key": False,
        },
        {
            "id": "proc-xml",
            "name": "XML Processor",
            "category": "processors",
            "description": "Parse and transform XML data",
            "version": "1.0.0",
            "size": "40KB",
            "installed": False,
            "requires_key": False,
        },
    ],
}

# Track installed plugins (in-memory, would be persistent in production)
_installed_plugins: set[str] = {
    "google-api",
    "groq-api",
    "mcp-browser",
    "mcp-search",
    "mcp-html",
    "skill-planner",
    "skill-navigator",
    "skill-extractor",
    "skill-verifier",
    "proc-json",
    "proc-csv",
}


class PluginAction(BaseModel):
    """Request to install/uninstall a plugin."""

    plugin_id: str = Field(..., description="Plugin identifier")


class PluginResponse(BaseModel):
    """Plugin information response."""

    id: str
    name: str
    category: str
    description: str
    version: str
    size: str
    installed: bool
    requires_key: bool


@router.get("")
@router.get("/")
async def list_plugins(category: str | None = None) -> dict[str, Any]:
    """List all available plugins, optionally filtered by category."""
    result = {}

    for cat, plugins in PLUGIN_REGISTRY.items():
        if category and cat != category:
            continue

        result[cat] = [
            {**plugin, "installed": plugin["id"] in _installed_plugins} for plugin in plugins
        ]

    # Calculate stats
    total = sum(len(plugins) for plugins in PLUGIN_REGISTRY.values())
    installed = len(_installed_plugins)

    return {
        "plugins": result,
        "categories": list(PLUGIN_REGISTRY.keys()),
        "stats": {
            "total": total,
            "installed": installed,
            "available": total - installed,
        },
    }


@router.get("/installed")
async def list_installed_plugins() -> dict[str, Any]:
    """List only installed plugins."""
    installed = []

    for plugins in PLUGIN_REGISTRY.values():
        for plugin in plugins:
            if plugin["id"] in _installed_plugins:
                installed.append({**plugin, "installed": True})

    return {
        "plugins": installed,
        "count": len(installed),
    }


@router.get("/{plugin_id}")
async def get_plugin(plugin_id: str) -> PluginResponse:
    """Get details about a specific plugin."""
    for plugins in PLUGIN_REGISTRY.values():
        for plugin in plugins:
            if plugin["id"] == plugin_id:
                return PluginResponse(**{**plugin, "installed": plugin_id in _installed_plugins})

    raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")


@router.post("/install")
async def install_plugin(action: PluginAction) -> dict[str, Any]:
    """Install a plugin."""
    plugin_id = action.plugin_id

    # Find the plugin
    plugin = None
    for plugins in PLUGIN_REGISTRY.values():
        for p in plugins:
            if p["id"] == plugin_id:
                plugin = p
                break

    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")

    if plugin_id in _installed_plugins:
        return {
            "status": "already_installed",
            "message": f"Plugin {plugin['name']} is already installed",
            "plugin": {**plugin, "installed": True},
        }

    # Install the plugin (in production, this would download/configure)
    _installed_plugins.add(plugin_id)

    return {
        "status": "success",
        "message": f"Plugin {plugin['name']} installed successfully",
        "plugin": {**plugin, "installed": True},
    }


@router.post("/uninstall")
async def uninstall_plugin(action: PluginAction) -> dict[str, Any]:
    """Uninstall a plugin."""
    plugin_id = action.plugin_id

    # Find the plugin
    plugin = None
    for plugins in PLUGIN_REGISTRY.values():
        for p in plugins:
            if p["id"] == plugin_id:
                plugin = p
                break

    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")

    if plugin_id not in _installed_plugins:
        return {
            "status": "not_installed",
            "message": f"Plugin {plugin['name']} is not installed",
            "plugin": {**plugin, "installed": False},
        }

    # Check if it's a core plugin
    core_plugins = {"mcp-browser", "mcp-search", "mcp-html", "skill-planner", "skill-navigator", "skill-extractor", "skill-verifier", "proc-json"}
    if plugin_id in core_plugins:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot uninstall core plugin: {plugin['name']}",
        )

    # Uninstall the plugin
    _installed_plugins.discard(plugin_id)

    return {
        "status": "success",
        "message": f"Plugin {plugin['name']} uninstalled successfully",
        "plugin": {**plugin, "installed": False},
    }


@router.get("/categories")
async def get_categories() -> dict[str, Any]:
    """Get plugin categories with descriptions."""
    return {
        "categories": [
            {"id": "apis", "name": "API Providers", "description": "LLM and AI service providers", "icon": "🔌"},
            {"id": "mcps", "name": "MCP Tools", "description": "Model Context Protocol tools", "icon": "🔧"},
            {"id": "skills", "name": "Skills/Agents", "description": "Specialized agent capabilities", "icon": "🤖"},
            {"id": "processors", "name": "Data Processors", "description": "Data transformation tools", "icon": "📊"},
        ],
    }
