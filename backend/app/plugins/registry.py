"""Plugin registry for scrapeRL - manages all available plugins and tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from enum import Enum


class PluginCategory(str, Enum):
    """Categories of plugins."""
    BROWSER = "browser"
    PARSER = "parser"
    DATA = "data"
    NETWORK = "network"
    MEDIA = "media"
    ANALYSIS = "analysis"
    EXTRACTION = "extraction"
    VALIDATION = "validation"
    STORAGE = "storage"
    AI = "ai"


@dataclass
class ToolDefinition:
    """Definition of a tool that can be called by agents."""
    name: str
    description: str
    category: PluginCategory
    parameters: dict[str, Any] = field(default_factory=dict)
    returns: dict[str, Any] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)


@dataclass
class PluginDefinition:
    """Definition of a plugin with its tools."""
    id: str
    name: str
    description: str
    category: PluginCategory
    tools: list[ToolDefinition] = field(default_factory=list)
    enabled: bool = True
    version: str = "1.0.0"


# ==============================================================================
# BROWSER TOOLS
# ==============================================================================

BROWSER_TOOLS = [
    ToolDefinition(
        name="browser.navigate",
        description="Navigate browser to a URL and wait for page load",
        category=PluginCategory.BROWSER,
        parameters={"url": "string", "wait_for": "string (page_load|network_idle)"},
        returns={"success": "bool", "html_length": "int", "status_code": "int"},
    ),
    ToolDefinition(
        name="browser.click",
        description="Click on an element matching the selector",
        category=PluginCategory.BROWSER,
        parameters={"selector": "string", "wait_after": "int (ms)"},
        returns={"clicked": "bool", "element_found": "bool"},
    ),
    ToolDefinition(
        name="browser.type",
        description="Type text into an input field",
        category=PluginCategory.BROWSER,
        parameters={"selector": "string", "text": "string", "clear_first": "bool"},
        returns={"typed": "bool", "element_found": "bool"},
    ),
    ToolDefinition(
        name="browser.scroll",
        description="Scroll the page or element",
        category=PluginCategory.BROWSER,
        parameters={"direction": "string (up|down|top|bottom)", "amount": "int (px)"},
        returns={"scrolled": "bool", "new_position": "int"},
    ),
    ToolDefinition(
        name="browser.screenshot",
        description="Capture a screenshot of the page or element",
        category=PluginCategory.BROWSER,
        parameters={"selector": "string (optional)", "full_page": "bool"},
        returns={"captured": "bool", "size_bytes": "int", "dimensions": "dict"},
    ),
    ToolDefinition(
        name="browser.wait",
        description="Wait for an element or condition",
        category=PluginCategory.BROWSER,
        parameters={"selector": "string", "timeout_ms": "int", "state": "string"},
        returns={"found": "bool", "waited_ms": "int"},
    ),
    ToolDefinition(
        name="browser.execute_js",
        description="Execute JavaScript in browser context",
        category=PluginCategory.BROWSER,
        parameters={"script": "string", "args": "list"},
        returns={"result": "any", "error": "string|null"},
    ),
    ToolDefinition(
        name="browser.get_cookies",
        description="Get cookies for current domain",
        category=PluginCategory.BROWSER,
        parameters={"domain": "string (optional)"},
        returns={"cookies": "list[dict]", "count": "int"},
    ),
]

# ==============================================================================
# HTML/DOM PARSING TOOLS
# ==============================================================================

HTML_TOOLS = [
    ToolDefinition(
        name="html.parse",
        description="Parse HTML document into structured DOM",
        category=PluginCategory.PARSER,
        parameters={"parser": "string (html.parser|lxml)", "content_length": "int"},
        returns={"parsed": "bool", "soup_type": "string"},
    ),
    ToolDefinition(
        name="html.select",
        description="Select elements using CSS selector",
        category=PluginCategory.PARSER,
        parameters={"selector": "string", "limit": "int (optional)"},
        returns={"elements_found": "int", "selector_used": "string"},
    ),
    ToolDefinition(
        name="html.select_one",
        description="Select first element matching CSS selector",
        category=PluginCategory.PARSER,
        parameters={"selector": "string"},
        returns={"found": "bool", "tag": "string", "text": "string"},
    ),
    ToolDefinition(
        name="html.find_all",
        description="Find all elements by tag and attributes (bs4)",
        category=PluginCategory.PARSER,
        parameters={"tag": "string", "attrs": "dict", "recursive": "bool"},
        returns={"elements_found": "int", "tags": "list[string]"},
    ),
    ToolDefinition(
        name="html.get_text",
        description="Extract text content from element or page",
        category=PluginCategory.PARSER,
        parameters={"selector": "string (optional)", "separator": "string"},
        returns={"text": "string", "length": "int"},
    ),
    ToolDefinition(
        name="html.get_attribute",
        description="Get attribute value from element",
        category=PluginCategory.PARSER,
        parameters={"selector": "string", "attribute": "string"},
        returns={"value": "string|null", "found": "bool"},
    ),
    ToolDefinition(
        name="html.extract_links",
        description="Extract all links from page",
        category=PluginCategory.PARSER,
        parameters={"base_url": "string", "filter_pattern": "string (optional)"},
        returns={"links": "list[dict]", "count": "int"},
    ),
    ToolDefinition(
        name="html.extract_images",
        description="Extract all images with src and alt",
        category=PluginCategory.PARSER,
        parameters={"include_lazy": "bool"},
        returns={"images": "list[dict]", "count": "int"},
    ),
    ToolDefinition(
        name="html.extract_tables",
        description="Extract HTML tables as structured data",
        category=PluginCategory.PARSER,
        parameters={"selector": "string (optional)"},
        returns={"tables": "list[list[list]]", "count": "int"},
    ),
    ToolDefinition(
        name="html.extract_forms",
        description="Extract form structure and fields",
        category=PluginCategory.PARSER,
        parameters={"selector": "string (optional)"},
        returns={"forms": "list[dict]", "count": "int"},
    ),
]

# ==============================================================================
# DATA PROCESSING TOOLS
# ==============================================================================

DATA_TOOLS = [
    ToolDefinition(
        name="json.parse",
        description="Parse JSON string into object",
        category=PluginCategory.DATA,
        parameters={"text": "string"},
        returns={"data": "any", "valid": "bool"},
    ),
    ToolDefinition(
        name="json.dumps",
        description="Convert object to JSON string",
        category=PluginCategory.DATA,
        parameters={"data": "any", "indent": "int", "sort_keys": "bool"},
        returns={"output": "string", "length": "int"},
    ),
    ToolDefinition(
        name="csv.generate",
        description="Generate CSV from data",
        category=PluginCategory.DATA,
        parameters={"data": "list[dict]", "fields": "list[string]"},
        returns={"csv": "string", "rows": "int", "columns": "int"},
    ),
    ToolDefinition(
        name="csv.parse",
        description="Parse CSV string into records",
        category=PluginCategory.DATA,
        parameters={"text": "string", "delimiter": "string", "has_header": "bool"},
        returns={"records": "list[dict]", "rows": "int", "columns": "int"},
    ),
    ToolDefinition(
        name="pandas.DataFrame",
        description="Create pandas DataFrame from data",
        category=PluginCategory.DATA,
        parameters={"data": "list[dict]|dict"},
        returns={"shape": "tuple", "columns": "list[string]", "dtypes": "dict"},
    ),
    ToolDefinition(
        name="pandas.read_csv",
        description="Read CSV data into DataFrame",
        category=PluginCategory.DATA,
        parameters={"content": "string", "sep": "string"},
        returns={"shape": "tuple", "columns": "list[string]"},
    ),
    ToolDefinition(
        name="pandas.to_csv",
        description="Convert DataFrame to CSV",
        category=PluginCategory.DATA,
        parameters={"index": "bool"},
        returns={"csv": "string", "rows": "int"},
    ),
    ToolDefinition(
        name="pandas.describe",
        description="Generate descriptive statistics",
        category=PluginCategory.DATA,
        parameters={"include": "string (all|numeric)"},
        returns={"statistics": "dict", "columns": "list[string]"},
    ),
    ToolDefinition(
        name="pandas.groupby",
        description="Group data by columns and aggregate",
        category=PluginCategory.DATA,
        parameters={"by": "list[string]", "agg": "dict"},
        returns={"groups": "int", "result": "dict"},
    ),
    ToolDefinition(
        name="pandas.filter",
        description="Filter DataFrame rows by condition",
        category=PluginCategory.DATA,
        parameters={"condition": "string"},
        returns={"filtered_rows": "int", "original_rows": "int"},
    ),
]

# ==============================================================================
# REGEX/TEXT TOOLS
# ==============================================================================

REGEX_TOOLS = [
    ToolDefinition(
        name="regex.match",
        description="Match pattern at start of string",
        category=PluginCategory.EXTRACTION,
        parameters={"pattern": "string", "text": "string", "flags": "string"},
        returns={"matched": "bool", "groups": "list[string]"},
    ),
    ToolDefinition(
        name="regex.search",
        description="Search for pattern anywhere in string",
        category=PluginCategory.EXTRACTION,
        parameters={"pattern": "string", "text": "string"},
        returns={"found": "bool", "position": "int", "match": "string"},
    ),
    ToolDefinition(
        name="regex.findall",
        description="Find all matches of pattern",
        category=PluginCategory.EXTRACTION,
        parameters={"pattern": "string", "text": "string"},
        returns={"matches": "list[string]", "count": "int"},
    ),
    ToolDefinition(
        name="regex.sub",
        description="Replace pattern matches in string",
        category=PluginCategory.EXTRACTION,
        parameters={"pattern": "string", "replacement": "string", "text": "string"},
        returns={"result": "string", "replacements": "int"},
    ),
    ToolDefinition(
        name="regex.split",
        description="Split string by pattern",
        category=PluginCategory.EXTRACTION,
        parameters={"pattern": "string", "text": "string", "maxsplit": "int"},
        returns={"parts": "list[string]", "count": "int"},
    ),
]

# ==============================================================================
# NETWORK/API TOOLS
# ==============================================================================

NETWORK_TOOLS = [
    ToolDefinition(
        name="http.get",
        description="Make HTTP GET request",
        category=PluginCategory.NETWORK,
        parameters={"url": "string", "headers": "dict", "timeout": "int"},
        returns={"status_code": "int", "content_length": "int", "headers": "dict"},
    ),
    ToolDefinition(
        name="http.post",
        description="Make HTTP POST request",
        category=PluginCategory.NETWORK,
        parameters={"url": "string", "data": "dict", "json": "dict", "headers": "dict"},
        returns={"status_code": "int", "response": "any"},
    ),
    ToolDefinition(
        name="http.head",
        description="Make HTTP HEAD request to get headers",
        category=PluginCategory.NETWORK,
        parameters={"url": "string", "timeout": "int"},
        returns={"status_code": "int", "headers": "dict"},
    ),
    ToolDefinition(
        name="url.parse",
        description="Parse URL into components",
        category=PluginCategory.NETWORK,
        parameters={"url": "string"},
        returns={"scheme": "string", "domain": "string", "path": "string", "params": "dict"},
    ),
    ToolDefinition(
        name="url.join",
        description="Join base URL with relative path",
        category=PluginCategory.NETWORK,
        parameters={"base": "string", "path": "string"},
        returns={"url": "string"},
    ),
]

# ==============================================================================
# MEDIA TOOLS
# ==============================================================================

MEDIA_TOOLS = [
    ToolDefinition(
        name="image.download",
        description="Download image from URL",
        category=PluginCategory.MEDIA,
        parameters={"url": "string", "timeout": "int"},
        returns={"size_bytes": "int", "format": "string", "dimensions": "dict"},
    ),
    ToolDefinition(
        name="image.analyze",
        description="Analyze image properties",
        category=PluginCategory.MEDIA,
        parameters={"url": "string"},
        returns={"width": "int", "height": "int", "format": "string", "has_transparency": "bool"},
    ),
    ToolDefinition(
        name="pdf.extract_text",
        description="Extract text content from PDF",
        category=PluginCategory.MEDIA,
        parameters={"url": "string", "pages": "list[int]"},
        returns={"text": "string", "pages": "int", "words": "int"},
    ),
    ToolDefinition(
        name="video.metadata",
        description="Extract video metadata",
        category=PluginCategory.MEDIA,
        parameters={"url": "string"},
        returns={"duration": "int", "resolution": "string", "format": "string"},
    ),
]

# ==============================================================================
# ANALYSIS TOOLS
# ==============================================================================

ANALYSIS_TOOLS = [
    ToolDefinition(
        name="stats.describe",
        description="Calculate descriptive statistics",
        category=PluginCategory.ANALYSIS,
        parameters={"data": "list[number]"},
        returns={"mean": "float", "median": "float", "std": "float", "min": "float", "max": "float"},
    ),
    ToolDefinition(
        name="stats.correlation",
        description="Calculate correlation between datasets",
        category=PluginCategory.ANALYSIS,
        parameters={"x": "list[number]", "y": "list[number]"},
        returns={"correlation": "float", "p_value": "float"},
    ),
    ToolDefinition(
        name="text.sentiment",
        description="Analyze sentiment of text",
        category=PluginCategory.ANALYSIS,
        parameters={"text": "string"},
        returns={"score": "float", "label": "string (positive|negative|neutral)"},
    ),
    ToolDefinition(
        name="text.entities",
        description="Extract named entities from text",
        category=PluginCategory.ANALYSIS,
        parameters={"text": "string", "types": "list[string]"},
        returns={"entities": "list[dict]", "count": "int"},
    ),
    ToolDefinition(
        name="text.keywords",
        description="Extract keywords from text",
        category=PluginCategory.ANALYSIS,
        parameters={"text": "string", "top_k": "int"},
        returns={"keywords": "list[string]", "scores": "list[float]"},
    ),
]

# ==============================================================================
# EXTRACTION TOOLS
# ==============================================================================

EXTRACTION_TOOLS = [
    ToolDefinition(
        name="extract.emails",
        description="Extract email addresses from text",
        category=PluginCategory.EXTRACTION,
        parameters={"text": "string"},
        returns={"emails": "list[string]", "count": "int"},
    ),
    ToolDefinition(
        name="extract.phones",
        description="Extract phone numbers from text",
        category=PluginCategory.EXTRACTION,
        parameters={"text": "string", "country_code": "string"},
        returns={"phones": "list[string]", "count": "int"},
    ),
    ToolDefinition(
        name="extract.urls",
        description="Extract URLs from text",
        category=PluginCategory.EXTRACTION,
        parameters={"text": "string"},
        returns={"urls": "list[string]", "count": "int"},
    ),
    ToolDefinition(
        name="extract.dates",
        description="Extract and parse dates from text",
        category=PluginCategory.EXTRACTION,
        parameters={"text": "string", "format": "string"},
        returns={"dates": "list[string]", "count": "int"},
    ),
    ToolDefinition(
        name="extract.prices",
        description="Extract prices and currencies from text",
        category=PluginCategory.EXTRACTION,
        parameters={"text": "string"},
        returns={"prices": "list[dict]", "count": "int"},
    ),
    ToolDefinition(
        name="extract.addresses",
        description="Extract physical addresses from text",
        category=PluginCategory.EXTRACTION,
        parameters={"text": "string"},
        returns={"addresses": "list[dict]", "count": "int"},
    ),
    ToolDefinition(
        name="extract.social_handles",
        description="Extract social media handles",
        category=PluginCategory.EXTRACTION,
        parameters={"text": "string", "platforms": "list[string]"},
        returns={"handles": "dict[string, list]", "count": "int"},
    ),
]

# ==============================================================================
# VALIDATION TOOLS
# ==============================================================================

VALIDATION_TOOLS = [
    ToolDefinition(
        name="validate.url",
        description="Validate URL format and accessibility",
        category=PluginCategory.VALIDATION,
        parameters={"url": "string", "check_accessibility": "bool"},
        returns={"valid": "bool", "accessible": "bool", "status_code": "int"},
    ),
    ToolDefinition(
        name="validate.email",
        description="Validate email format",
        category=PluginCategory.VALIDATION,
        parameters={"email": "string"},
        returns={"valid": "bool", "normalized": "string"},
    ),
    ToolDefinition(
        name="validate.json",
        description="Validate JSON format",
        category=PluginCategory.VALIDATION,
        parameters={"text": "string"},
        returns={"valid": "bool", "error": "string|null"},
    ),
    ToolDefinition(
        name="validate.html",
        description="Validate HTML structure",
        category=PluginCategory.VALIDATION,
        parameters={"html": "string"},
        returns={"valid": "bool", "errors": "list[string]"},
    ),
    ToolDefinition(
        name="validate.schema",
        description="Validate data against JSON schema",
        category=PluginCategory.VALIDATION,
        parameters={"data": "any", "schema": "dict"},
        returns={"valid": "bool", "errors": "list[string]"},
    ),
]

# ==============================================================================
# STORAGE TOOLS
# ==============================================================================

STORAGE_TOOLS = [
    ToolDefinition(
        name="memory.store",
        description="Store data in long-term memory",
        category=PluginCategory.STORAGE,
        parameters={"key": "string", "value": "any", "ttl": "int"},
        returns={"stored": "bool", "key": "string"},
    ),
    ToolDefinition(
        name="memory.retrieve",
        description="Retrieve data from memory",
        category=PluginCategory.STORAGE,
        parameters={"key": "string"},
        returns={"found": "bool", "value": "any"},
    ),
    ToolDefinition(
        name="memory.search",
        description="Search memory by semantic similarity",
        category=PluginCategory.STORAGE,
        parameters={"query": "string", "limit": "int"},
        returns={"results": "list[dict]", "count": "int"},
    ),
    ToolDefinition(
        name="cache.get",
        description="Get value from session cache",
        category=PluginCategory.STORAGE,
        parameters={"key": "string"},
        returns={"found": "bool", "value": "any"},
    ),
    ToolDefinition(
        name="cache.set",
        description="Set value in session cache",
        category=PluginCategory.STORAGE,
        parameters={"key": "string", "value": "any"},
        returns={"stored": "bool"},
    ),
]

# ==============================================================================
# SANDBOX TOOLS
# ==============================================================================

SANDBOX_TOOLS = [
    ToolDefinition(
        name="sandbox.execute",
        description="Execute Python code in sandboxed environment",
        category=PluginCategory.AI,
        parameters={"code": "string", "payload": "dict", "timeout": "int"},
        returns={"success": "bool", "output": "any", "stdout": "string"},
    ),
    ToolDefinition(
        name="sandbox.analyze",
        description="Run data analysis in sandbox",
        category=PluginCategory.AI,
        parameters={"data": "list[dict]", "analysis_type": "string"},
        returns={"result": "dict", "visualizations": "list"},
    ),
    ToolDefinition(
        name="sandbox.transform",
        description="Transform data using sandbox code",
        category=PluginCategory.AI,
        parameters={"data": "any", "transform_code": "string"},
        returns={"transformed": "any", "success": "bool"},
    ),
]

# ==============================================================================
# AI TOOLS
# ==============================================================================

AI_TOOLS = [
    ToolDefinition(
        name="ai.complete",
        description="Generate text completion using AI model",
        category=PluginCategory.AI,
        parameters={"prompt": "string", "model": "string", "max_tokens": "int"},
        returns={"text": "string", "tokens_used": "int"},
    ),
    ToolDefinition(
        name="ai.embed",
        description="Generate embeddings for text",
        category=PluginCategory.AI,
        parameters={"text": "string", "model": "string"},
        returns={"embedding": "list[float]", "dimensions": "int"},
    ),
    ToolDefinition(
        name="ai.classify",
        description="Classify text into categories",
        category=PluginCategory.AI,
        parameters={"text": "string", "labels": "list[string]"},
        returns={"label": "string", "confidence": "float"},
    ),
    ToolDefinition(
        name="ai.summarize",
        description="Summarize text content",
        category=PluginCategory.AI,
        parameters={"text": "string", "max_length": "int"},
        returns={"summary": "string", "reduction_ratio": "float"},
    ),
]

# ==============================================================================
# PLUGIN DEFINITIONS
# ==============================================================================

PLUGINS: list[PluginDefinition] = [
    PluginDefinition(
        id="browser",
        name="Browser Automation",
        description="Control browser navigation, clicks, typing, and screenshots",
        category=PluginCategory.BROWSER,
        tools=BROWSER_TOOLS,
    ),
    PluginDefinition(
        id="html-parser",
        name="HTML/DOM Parser",
        description="Parse and query HTML documents using BeautifulSoup",
        category=PluginCategory.PARSER,
        tools=HTML_TOOLS,
    ),
    PluginDefinition(
        id="data-processing",
        name="Data Processing",
        description="JSON, CSV, and Pandas data processing tools",
        category=PluginCategory.DATA,
        tools=DATA_TOOLS,
    ),
    PluginDefinition(
        id="regex",
        name="Regular Expressions",
        description="Pattern matching and text extraction using regex",
        category=PluginCategory.EXTRACTION,
        tools=REGEX_TOOLS,
    ),
    PluginDefinition(
        id="network",
        name="Network/HTTP",
        description="HTTP requests and URL handling",
        category=PluginCategory.NETWORK,
        tools=NETWORK_TOOLS,
    ),
    PluginDefinition(
        id="media",
        name="Media Processing",
        description="Image, PDF, and video processing tools",
        category=PluginCategory.MEDIA,
        tools=MEDIA_TOOLS,
    ),
    PluginDefinition(
        id="analysis",
        name="Analysis",
        description="Statistical analysis and NLP tools",
        category=PluginCategory.ANALYSIS,
        tools=ANALYSIS_TOOLS,
    ),
    PluginDefinition(
        id="extraction",
        name="Data Extraction",
        description="Extract structured data like emails, phones, addresses",
        category=PluginCategory.EXTRACTION,
        tools=EXTRACTION_TOOLS,
    ),
    PluginDefinition(
        id="validation",
        name="Validation",
        description="Validate URLs, emails, JSON, HTML, and schemas",
        category=PluginCategory.VALIDATION,
        tools=VALIDATION_TOOLS,
    ),
    PluginDefinition(
        id="storage",
        name="Storage/Memory",
        description="Long-term memory and session cache",
        category=PluginCategory.STORAGE,
        tools=STORAGE_TOOLS,
    ),
    PluginDefinition(
        id="sandbox",
        name="Python Sandbox",
        description="Execute Python code in isolated sandbox",
        category=PluginCategory.AI,
        tools=SANDBOX_TOOLS,
    ),
    PluginDefinition(
        id="ai",
        name="AI/LLM",
        description="AI completion, embeddings, and classification",
        category=PluginCategory.AI,
        tools=AI_TOOLS,
    ),
]


def get_all_plugins() -> list[PluginDefinition]:
    """Get all registered plugins."""
    return PLUGINS


def get_plugin(plugin_id: str) -> Optional[PluginDefinition]:
    """Get plugin by ID."""
    for plugin in PLUGINS:
        if plugin.id == plugin_id:
            return plugin
    return None


def get_all_tools() -> list[ToolDefinition]:
    """Get all registered tools across all plugins."""
    tools = []
    for plugin in PLUGINS:
        tools.extend(plugin.tools)
    return tools


def get_tool(tool_name: str) -> Optional[ToolDefinition]:
    """Get tool definition by name."""
    for plugin in PLUGINS:
        for tool in plugin.tools:
            if tool.name == tool_name:
                return tool
    return None


def get_tools_by_category(category: PluginCategory) -> list[ToolDefinition]:
    """Get all tools in a category."""
    tools = []
    for plugin in PLUGINS:
        if plugin.category == category:
            tools.extend(plugin.tools)
    return tools


def get_plugin_summary() -> dict[str, Any]:
    """Get summary of all plugins and tools."""
    return {
        "plugins_count": len(PLUGINS),
        "tools_count": sum(len(p.tools) for p in PLUGINS),
        "categories": list(set(p.category.value for p in PLUGINS)),
        "plugins": [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category.value,
                "tools_count": len(p.tools),
            }
            for p in PLUGINS
        ],
    }
