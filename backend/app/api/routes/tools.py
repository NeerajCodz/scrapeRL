"""Tool registry and testing endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/tools")
logger = logging.getLogger(__name__)


class ToolParameter(BaseModel):
    """Parameter definition for a tool."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any | None = None


class ToolDefinition(BaseModel):
    """Definition of a tool in the registry."""

    name: str
    description: str
    category: str
    parameters: list[ToolParameter]
    returns: str
    examples: list[dict[str, Any]] = Field(default_factory=list)
    requires_browser: bool = False
    cost_estimate: float = 0.0


class ToolRegistryResponse(BaseModel):
    """Response containing the tool registry."""

    tools: list[ToolDefinition]
    categories: list[str]
    total_count: int


class ToolTestRequest(BaseModel):
    """Request to test a tool."""

    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True


class ToolTestResponse(BaseModel):
    """Response from tool testing."""

    tool_name: str
    success: bool
    result: Any | None = None
    error: str | None = None
    execution_time_ms: float = 0.0
    dry_run: bool


# Tool definitions (would be dynamically registered in production)
TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="navigate_to",
        description="Navigate the browser to a specified URL",
        category="browser",
        parameters=[
            ToolParameter(name="url", type="string", description="URL to navigate to"),
            ToolParameter(name="wait_for", type="string", description="CSS selector to wait for", required=False),
        ],
        returns="NavigationResult with page info",
        requires_browser=True,
        cost_estimate=0.01,
    ),
    ToolDefinition(
        name="click_element",
        description="Click on an element identified by selector",
        category="browser",
        parameters=[
            ToolParameter(name="selector", type="string", description="CSS selector of element to click"),
        ],
        returns="ClickResult with success status",
        requires_browser=True,
        cost_estimate=0.005,
    ),
    ToolDefinition(
        name="extract_text",
        description="Extract text content from elements",
        category="extraction",
        parameters=[
            ToolParameter(name="selector", type="string", description="CSS selector to extract from"),
            ToolParameter(name="multiple", type="boolean", description="Extract from all matches", default=False),
        ],
        returns="Extracted text or list of texts",
        requires_browser=True,
        cost_estimate=0.002,
    ),
    ToolDefinition(
        name="extract_attribute",
        description="Extract attribute value from element",
        category="extraction",
        parameters=[
            ToolParameter(name="selector", type="string", description="CSS selector"),
            ToolParameter(name="attribute", type="string", description="Attribute name to extract"),
        ],
        returns="Attribute value",
        requires_browser=True,
        cost_estimate=0.002,
    ),
    ToolDefinition(
        name="search_engine",
        description="Perform a search using a search engine",
        category="search",
        parameters=[
            ToolParameter(name="query", type="string", description="Search query"),
            ToolParameter(name="engine", type="string", description="Search engine", default="google"),
            ToolParameter(name="num_results", type="integer", description="Number of results", default=10),
        ],
        returns="List of search results",
        cost_estimate=0.05,
    ),
    ToolDefinition(
        name="fill_form",
        description="Fill a form field with a value",
        category="browser",
        parameters=[
            ToolParameter(name="selector", type="string", description="CSS selector of form field"),
            ToolParameter(name="value", type="string", description="Value to fill"),
        ],
        returns="FillResult with success status",
        requires_browser=True,
        cost_estimate=0.005,
    ),
    ToolDefinition(
        name="screenshot",
        description="Take a screenshot of the current page",
        category="browser",
        parameters=[
            ToolParameter(name="full_page", type="boolean", description="Capture full page", default=False),
        ],
        returns="Base64 encoded screenshot",
        requires_browser=True,
        cost_estimate=0.01,
    ),
    ToolDefinition(
        name="get_page_html",
        description="Get the full HTML content of the current page",
        category="extraction",
        parameters=[],
        returns="HTML string",
        requires_browser=True,
        cost_estimate=0.001,
    ),
    ToolDefinition(
        name="wait_for_selector",
        description="Wait for an element to appear on the page",
        category="browser",
        parameters=[
            ToolParameter(name="selector", type="string", description="CSS selector to wait for"),
            ToolParameter(name="timeout_ms", type="integer", description="Timeout in milliseconds", default=30000),
        ],
        returns="Boolean indicating if element appeared",
        requires_browser=True,
        cost_estimate=0.001,
    ),
    ToolDefinition(
        name="scroll_to",
        description="Scroll to a position or element",
        category="browser",
        parameters=[
            ToolParameter(name="selector", type="string", description="CSS selector", required=False),
            ToolParameter(name="position", type="string", description="Position: top, bottom, or pixel value", required=False),
        ],
        returns="ScrollResult",
        requires_browser=True,
        cost_estimate=0.001,
    ),
]


@router.get(
    "/registry",
    response_model=ToolRegistryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get tool registry",
    description="Get all available tools in the registry",
)
async def get_tool_registry(category: str | None = None) -> ToolRegistryResponse:
    """
    Get the tool registry with all available tools.
    
    Args:
        category: Optional filter by category.
    
    Returns:
        ToolRegistryResponse: List of available tools.
    """
    tools = TOOL_DEFINITIONS
    if category:
        tools = [t for t in tools if t.category == category]

    categories = list(set(t.category for t in TOOL_DEFINITIONS))

    return ToolRegistryResponse(
        tools=tools,
        categories=categories,
        total_count=len(tools),
    )


@router.get(
    "/registry/{tool_name}",
    response_model=ToolDefinition,
    status_code=status.HTTP_200_OK,
    summary="Get tool details",
    description="Get details of a specific tool",
)
async def get_tool_details(tool_name: str) -> ToolDefinition:
    """
    Get details of a specific tool.
    
    Args:
        tool_name: Name of the tool.
    
    Returns:
        ToolDefinition: Tool details.
    """
    for tool in TOOL_DEFINITIONS:
        if tool.name == tool_name:
            return tool
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Tool '{tool_name}' not found",
    )


@router.post(
    "/test",
    response_model=ToolTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Test a tool",
    description="Test a tool with provided parameters",
)
async def test_tool(request: ToolTestRequest) -> ToolTestResponse:
    """
    Test a tool execution.
    
    Args:
        request: Tool test request.
    
    Returns:
        ToolTestResponse: Result of tool test.
    """
    import time

    start_time = time.time()
    logger.info(f"Testing tool '{request.tool_name}' with dry_run={request.dry_run}")

    # Find the tool
    tool = None
    for t in TOOL_DEFINITIONS:
        if t.name == request.tool_name:
            tool = t
            break

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{request.tool_name}' not found",
        )

    try:
        # Validate required parameters
        for param in tool.parameters:
            if param.required and param.name not in request.parameters:
                raise ValueError(f"Missing required parameter: {param.name}")

        if request.dry_run:
            # Return mock result for dry run
            result = {
                "status": "dry_run",
                "tool": request.tool_name,
                "parameters": request.parameters,
                "would_require_browser": tool.requires_browser,
            }
        else:
            # Actually execute the tool (placeholder)
            from app.tools.registry import MCPToolRegistry
            registry = MCPToolRegistry()
            result = await registry.execute_tool(request.tool_name, request.parameters)

        execution_time = (time.time() - start_time) * 1000

        return ToolTestResponse(
            tool_name=request.tool_name,
            success=True,
            result=result,
            execution_time_ms=execution_time,
            dry_run=request.dry_run,
        )
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"Tool test failed: {e}")
        return ToolTestResponse(
            tool_name=request.tool_name,
            success=False,
            error=str(e),
            execution_time_ms=execution_time,
            dry_run=request.dry_run,
        )


@router.get(
    "/categories",
    status_code=status.HTTP_200_OK,
    summary="Get tool categories",
    description="Get all tool categories",
)
async def get_categories() -> dict[str, Any]:
    """
    Get all tool categories.
    
    Returns:
        Dict with category information.
    """
    categories = {}
    for tool in TOOL_DEFINITIONS:
        if tool.category not in categories:
            categories[tool.category] = []
        categories[tool.category].append(tool.name)
    return {"categories": categories}
