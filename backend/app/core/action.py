"""Action model for the RL environment."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActionType(str, Enum):
    """All possible action types in the environment."""

    # Navigation actions
    NAVIGATE = "navigate"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    REFRESH = "refresh"

    # Interaction actions
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    SCROLL = "scroll"
    HOVER = "hover"

    # Extraction actions
    EXTRACT_FIELD = "extract_field"
    EXTRACT_TABLE = "extract_table"
    EXTRACT_LIST = "extract_list"

    # Search actions
    SEARCH_PAGE = "search_page"
    SEARCH_ENGINE = "search_engine"

    # Verification actions
    VERIFY_FACT = "verify_fact"
    VERIFY_FIELD = "verify_field"

    # Memory actions
    STORE_MEMORY = "store_memory"
    RECALL_MEMORY = "recall_memory"

    # Tool actions
    MCP_TOOL_CALL = "mcp_tool_call"

    # Planning actions
    CREATE_PLAN = "create_plan"
    UPDATE_PLAN = "update_plan"

    # Communication actions
    SEND_MESSAGE = "send_message"

    # Control actions
    WAIT = "wait"
    DONE = "done"
    FAIL = "fail"


class NavigateParams(BaseModel):
    """Parameters for navigation actions."""

    url: str
    wait_for: str | None = None
    timeout_ms: int = 30000


class ClickParams(BaseModel):
    """Parameters for click actions."""

    selector: str
    button: str = "left"
    click_count: int = 1
    wait_after_ms: int = 500


class FillParams(BaseModel):
    """Parameters for form fill actions."""

    selector: str
    value: str
    clear_first: bool = True


class SelectParams(BaseModel):
    """Parameters for select dropdown actions."""

    selector: str
    value: str | None = None
    label: str | None = None
    index: int | None = None


class ScrollParams(BaseModel):
    """Parameters for scroll actions."""

    direction: str = "down"
    amount: int | str = "page"
    selector: str | None = None


class ExtractFieldParams(BaseModel):
    """Parameters for field extraction actions."""

    field_name: str
    selector: str | None = None
    extraction_method: str = "text"
    attribute: str | None = None
    regex_pattern: str | None = None
    post_process: str | None = None


class ExtractTableParams(BaseModel):
    """Parameters for table extraction actions."""

    table_selector: str
    headers: list[str] | None = None
    row_selector: str | None = None
    cell_selectors: dict[str, str] | None = None


class ExtractListParams(BaseModel):
    """Parameters for list extraction actions."""

    container_selector: str
    item_selector: str
    field_selectors: dict[str, str]


class SearchPageParams(BaseModel):
    """Parameters for searching within the current page."""

    query: str
    search_type: str = "text"


class SearchEngineParams(BaseModel):
    """Parameters for search engine queries."""

    query: str
    engine: str = "google"
    num_results: int = 10


class VerifyFactParams(BaseModel):
    """Parameters for fact verification."""

    claim: str
    sources: list[str] | None = None
    confidence_threshold: float = 0.8


class VerifyFieldParams(BaseModel):
    """Parameters for field verification."""

    field_name: str
    expected_type: str | None = None
    expected_format: str | None = None
    validation_rules: list[str] = Field(default_factory=list)


class MemoryParams(BaseModel):
    """Parameters for memory operations."""

    key: str
    value: Any | None = None
    memory_type: str = "working"
    ttl_seconds: int | None = None


class MCPToolCallParams(BaseModel):
    """Parameters for MCP tool calls."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class PlanParams(BaseModel):
    """Parameters for planning actions."""

    plan_description: str | None = None
    steps: list[dict[str, Any]] | None = None


class MessageParams(BaseModel):
    """Parameters for inter-agent messages."""

    target_agent: str
    message_type: str
    content: dict[str, Any] = Field(default_factory=dict)


class WaitParams(BaseModel):
    """Parameters for wait actions."""

    duration_ms: int = 1000
    wait_for_selector: str | None = None
    wait_for_navigation: bool = False


class DoneParams(BaseModel):
    """Parameters for completion."""

    success: bool = True
    message: str | None = None
    final_result: dict[str, Any] | None = None


class Action(BaseModel):
    """
    Represents an action to be taken in the environment.
    
    An action consists of:
    - action_type: The type of action
    - parameters: Action-specific parameters
    - reasoning: Why this action was chosen
    - confidence: How confident the agent is
    """

    action_type: ActionType = Field(..., description="Type of action to execute")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific parameters",
    )
    reasoning: str | None = Field(
        default=None,
        description="Agent's reasoning for this action",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this action (0-1)",
    )
    agent_id: str | None = Field(
        default=None,
        description="ID of the agent that produced this action",
    )
    plan_step: int | None = Field(
        default=None,
        description="Which step of the plan this corresponds to",
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        return max(0.0, min(1.0, v))

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action_type": "extract_field",
                "parameters": {
                    "field_name": "price",
                    "selector": ".product-price",
                    "extraction_method": "text",
                },
                "reasoning": "The price element is visible with class .product-price",
                "confidence": 0.92,
            }
        }
    )

    @classmethod
    def navigate(cls, url: str, **kwargs: Any) -> "Action":
        """Create a navigate action."""
        return cls(
            action_type=ActionType.NAVIGATE,
            parameters={"url": url, **kwargs},
        )

    @classmethod
    def click(cls, selector: str, **kwargs: Any) -> "Action":
        """Create a click action."""
        return cls(
            action_type=ActionType.CLICK,
            parameters={"selector": selector, **kwargs},
        )

    @classmethod
    def extract_field(
        cls,
        field_name: str,
        selector: str | None = None,
        **kwargs: Any,
    ) -> "Action":
        """Create an extract field action."""
        return cls(
            action_type=ActionType.EXTRACT_FIELD,
            parameters={"field_name": field_name, "selector": selector, **kwargs},
        )

    @classmethod
    def search_engine(cls, query: str, engine: str = "google", **kwargs: Any) -> "Action":
        """Create a search engine action."""
        return cls(
            action_type=ActionType.SEARCH_ENGINE,
            parameters={"query": query, "engine": engine, **kwargs},
        )

    @classmethod
    def done(cls, success: bool = True, message: str | None = None) -> "Action":
        """Create a done action."""
        return cls(
            action_type=ActionType.DONE,
            parameters={"success": success, "message": message},
        )

    @classmethod
    def wait(cls, duration_ms: int = 1000) -> "Action":
        """Create a wait action."""
        return cls(
            action_type=ActionType.WAIT,
            parameters={"duration_ms": duration_ms},
        )

    @classmethod
    def mcp_tool_call(cls, tool_name: str, **arguments: Any) -> "Action":
        """Create an MCP tool call action."""
        return cls(
            action_type=ActionType.MCP_TOOL_CALL,
            parameters={"tool_name": tool_name, "arguments": arguments},
        )

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get a parameter value with optional default."""
        return self.parameters.get(key, default)

    def validate_params(self) -> list[str]:
        """Validate parameters for this action type. Returns list of errors."""
        errors = []

        required_params = {
            ActionType.NAVIGATE: ["url"],
            ActionType.CLICK: ["selector"],
            ActionType.FILL: ["selector", "value"],
            ActionType.EXTRACT_FIELD: ["field_name"],
            ActionType.SEARCH_ENGINE: ["query"],
            ActionType.MCP_TOOL_CALL: ["tool_name"],
            ActionType.SEND_MESSAGE: ["target_agent", "message_type"],
        }

        if self.action_type in required_params:
            for param in required_params[self.action_type]:
                if param not in self.parameters or self.parameters[param] is None:
                    errors.append(f"Missing required parameter: {param}")

        return errors
