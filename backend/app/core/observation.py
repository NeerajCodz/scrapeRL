"""Observation model for the RL environment."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolSnapshot(BaseModel):
    """Snapshot of a tool from the registry."""

    name: str
    description: str
    parameters: list[dict[str, Any]]
    enabled: bool = True
    cost_estimate: float = 0.0


class MemoryContext(BaseModel):
    """Context from memory systems."""

    short_term: list[dict[str, Any]] = Field(default_factory=list)
    working: list[dict[str, Any]] = Field(default_factory=list)
    long_term_relevant: list[dict[str, Any]] = Field(default_factory=list)
    shared: dict[str, Any] = Field(default_factory=dict)


class PageElement(BaseModel):
    """A significant element on the page."""

    selector: str
    tag: str
    text: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    is_interactive: bool = False
    is_visible: bool = True
    bounding_box: dict[str, float] | None = None


class ExtractedField(BaseModel):
    """A field that has been extracted."""

    field_name: str
    value: Any
    confidence: float = 1.0
    source_selector: str | None = None
    extraction_step: int = 0
    verified: bool = False


class AvailableAction(BaseModel):
    """An action that is currently available."""

    action_type: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    estimated_reward: float | None = None
    risk_level: str = "low"


class TaskContext(BaseModel):
    """Context about the current task."""

    task_id: str
    task_name: str
    task_type: str
    target_fields: list[str]
    required_fields: list[str]
    hints: list[str] = Field(default_factory=list)
    success_criteria: dict[str, Any] = Field(default_factory=dict)


class Observation(BaseModel):
    """
    Complete observation provided to the agent after each step.
    
    Contains all information the agent needs to make decisions:
    - Episode and task context
    - Current page state
    - Extracted data so far
    - Memory context
    - Available tools and actions
    """

    # Episode identification
    episode_id: str = Field(..., description="Unique episode identifier")
    task_id: str = Field(..., description="Task being executed")
    step_number: int = Field(..., description="Current step in the episode")

    # Timing
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    elapsed_seconds: float = Field(default=0.0, description="Time elapsed in episode")

    # Page state
    current_url: str | None = Field(default=None, description="Current page URL")
    page_title: str | None = Field(default=None, description="Current page title")
    page_html: str | None = Field(default=None, description="Full HTML of current page")
    page_html_chunked: list[str] = Field(
        default_factory=list,
        description="HTML split into semantic chunks",
    )
    page_text: str | None = Field(default=None, description="Visible text content")
    page_elements: list[PageElement] = Field(
        default_factory=list,
        description="Significant page elements",
    )

    # Navigation state
    navigation_history: list[str] = Field(
        default_factory=list,
        description="URLs visited in this episode",
    )
    can_go_back: bool = Field(default=False)
    can_go_forward: bool = Field(default=False)

    # Task context
    task_context: TaskContext | None = Field(
        default=None,
        description="Information about the current task",
    )

    # Extraction state
    extracted_so_far: list[ExtractedField] = Field(
        default_factory=list,
        description="Fields extracted so far",
    )
    extraction_progress: float = Field(
        default=0.0,
        description="Progress towards task completion (0-1)",
    )
    fields_remaining: list[str] = Field(
        default_factory=list,
        description="Fields still to be extracted",
    )

    # Memory context
    memory_context: MemoryContext = Field(
        default_factory=MemoryContext,
        description="Relevant memories from all layers",
    )

    # Tool registry snapshot
    tool_registry_snapshot: list[ToolSnapshot] = Field(
        default_factory=list,
        description="Available tools and their state",
    )

    # Available actions
    available_actions: list[AvailableAction] = Field(
        default_factory=list,
        description="Actions available in current state",
    )

    # Agent coordination
    pending_messages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Messages from other agents",
    )
    active_plan: dict[str, Any] | None = Field(
        default=None,
        description="Current execution plan if any",
    )
    current_plan_step: int | None = Field(
        default=None,
        description="Current step in the plan",
    )

    # Error state
    last_action_error: str | None = Field(
        default=None,
        description="Error from last action if any",
    )
    consecutive_errors: int = Field(
        default=0,
        description="Number of consecutive action errors",
    )

    # Cost tracking
    tokens_used: int = Field(default=0, description="LLM tokens used so far")
    api_calls_made: int = Field(default=0, description="API calls made")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated cost so far")

    # Hints and guidance
    system_hints: list[str] = Field(
        default_factory=list,
        description="Hints from the environment or previous steps",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "episode_id": "ep_abc123",
                "task_id": "task_001",
                "step_number": 5,
                "current_url": "https://example.com/product/123",
                "page_title": "Product Details - Example Store",
                "extracted_so_far": [
                    {
                        "field_name": "product_name",
                        "value": "Example Product",
                        "confidence": 0.95,
                    }
                ],
                "extraction_progress": 0.33,
                "fields_remaining": ["price", "description"],
            }
        }
    )

    def get_extraction_dict(self) -> dict[str, Any]:
        """Get extracted fields as a dictionary."""
        return {field.field_name: field.value for field in self.extracted_so_far}

    def is_field_extracted(self, field_name: str) -> bool:
        """Check if a field has been extracted."""
        return any(f.field_name == field_name for f in self.extracted_so_far)

    def get_context_summary(self) -> str:
        """Get a summary of the current context for LLM prompts."""
        parts = [
            f"Step {self.step_number}",
            f"URL: {self.current_url or 'None'}",
            f"Progress: {self.extraction_progress:.0%}",
            f"Extracted: {len(self.extracted_so_far)}/{len(self.extracted_so_far) + len(self.fields_remaining)} fields",
        ]
        if self.last_action_error:
            parts.append(f"Last error: {self.last_action_error}")
        return " | ".join(parts)
