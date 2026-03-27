"""Tasks management endpoints."""

import logging
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/tasks")
logger = logging.getLogger(__name__)


class TaskDifficulty(str, Enum):
    """Task difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class TaskType(str, Enum):
    """Types of scraping tasks."""

    SINGLE_PAGE = "single_page"
    MULTI_PAGE = "multi_page"
    SEARCH_EXTRACT = "search_extract"
    FORM_FILL = "form_fill"
    DYNAMIC_CONTENT = "dynamic_content"
    AUTHENTICATION = "authentication"


class FieldSchema(BaseModel):
    """Schema for a field to extract."""

    name: str
    description: str
    field_type: str = "string"
    required: bool = True
    validation_pattern: str | None = None


class Task(BaseModel):
    """A scraping task definition."""

    id: str
    name: str
    description: str
    task_type: TaskType
    difficulty: TaskDifficulty
    target_url: str | None = None
    target_domain: str | None = None
    fields_to_extract: list[FieldSchema]
    success_criteria: dict[str, Any]
    hints: list[str] = Field(default_factory=list)
    max_steps: int = 50
    timeout_seconds: float = 300.0
    tags: list[str] = Field(default_factory=list)


class TaskListResponse(BaseModel):
    """Response for listing tasks."""

    tasks: list[Task]
    total: int
    page: int
    page_size: int


class TaskProgress(BaseModel):
    """Progress on a task within an episode."""

    task_id: str
    fields_extracted: int
    fields_total: int
    steps_taken: int
    max_steps: int
    accuracy_estimate: float
    completion_percentage: float


# Sample task repository (would be database-backed in production)
TASK_REPOSITORY: dict[str, Task] = {
    "task_001": Task(
        id="task_001",
        name="Extract Product Details",
        description="Extract product name, price, and description from an e-commerce page",
        task_type=TaskType.SINGLE_PAGE,
        difficulty=TaskDifficulty.EASY,
        target_url="https://example.com/product/123",
        fields_to_extract=[
            FieldSchema(name="product_name", description="The name of the product"),
            FieldSchema(name="price", description="Current price", field_type="number"),
            FieldSchema(name="description", description="Product description"),
        ],
        success_criteria={"min_accuracy": 0.9, "required_fields": ["product_name", "price"]},
        hints=["Look for h1 tags for product name", "Price often in span with class containing 'price'"],
        tags=["ecommerce", "product"],
    ),
    "task_002": Task(
        id="task_002",
        name="Search and Extract Company Info",
        description="Search for a company and extract key information from search results",
        task_type=TaskType.SEARCH_EXTRACT,
        difficulty=TaskDifficulty.MEDIUM,
        target_domain="linkedin.com",
        fields_to_extract=[
            FieldSchema(name="company_name", description="Official company name"),
            FieldSchema(name="industry", description="Primary industry"),
            FieldSchema(name="employee_count", description="Number of employees", field_type="string"),
            FieldSchema(name="headquarters", description="Location of headquarters"),
        ],
        success_criteria={"min_accuracy": 0.8, "required_fields": ["company_name", "industry"]},
        tags=["search", "company", "linkedin"],
        max_steps=30,
    ),
    "task_003": Task(
        id="task_003",
        name="Multi-page Article Extraction",
        description="Navigate through paginated articles and extract all content",
        task_type=TaskType.MULTI_PAGE,
        difficulty=TaskDifficulty.HARD,
        target_domain="news-site.example.com",
        fields_to_extract=[
            FieldSchema(name="articles", description="List of article data", field_type="array"),
        ],
        success_criteria={"min_articles": 10, "min_accuracy": 0.85},
        tags=["pagination", "articles", "news"],
        max_steps=100,
    ),
}


@router.get(
    "/",
    response_model=TaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List available tasks",
    description="Get a paginated list of available scraping tasks",
)
async def list_tasks(
    page: int = 1,
    page_size: int = 20,
    difficulty: TaskDifficulty | None = None,
    task_type: TaskType | None = None,
    tag: str | None = None,
) -> TaskListResponse:
    """
    List available tasks with optional filtering.
    
    Args:
        page: Page number (1-indexed).
        page_size: Number of tasks per page.
        difficulty: Filter by difficulty level.
        task_type: Filter by task type.
        tag: Filter by tag.
    
    Returns:
        TaskListResponse: Paginated list of tasks.
    """
    tasks = list(TASK_REPOSITORY.values())

    # Apply filters
    if difficulty:
        tasks = [t for t in tasks if t.difficulty == difficulty]
    if task_type:
        tasks = [t for t in tasks if t.task_type == task_type]
    if tag:
        tasks = [t for t in tasks if tag in t.tags]

    # Paginate
    total = len(tasks)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_tasks = tasks[start:end]

    return TaskListResponse(
        tasks=paginated_tasks,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{task_id}",
    response_model=Task,
    status_code=status.HTTP_200_OK,
    summary="Get task details",
    description="Get details of a specific task",
)
async def get_task(task_id: str) -> Task:
    """
    Get details of a specific task.
    
    Args:
        task_id: ID of the task.
    
    Returns:
        Task: Task details.
    """
    if task_id not in TASK_REPOSITORY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return TASK_REPOSITORY[task_id]


@router.post(
    "/",
    response_model=Task,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    description="Create a new scraping task",
)
async def create_task(task: Task) -> Task:
    """
    Create a new task.
    
    Args:
        task: Task definition.
    
    Returns:
        Task: Created task.
    """
    if task.id in TASK_REPOSITORY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task {task.id} already exists",
        )
    TASK_REPOSITORY[task.id] = task
    logger.info(f"Created task {task.id}: {task.name}")
    return task


@router.get(
    "/types/",
    status_code=status.HTTP_200_OK,
    summary="Get task types",
    description="Get all available task types",
)
async def get_task_types() -> dict[str, list[str]]:
    """
    Get available task types and difficulties.
    
    Returns:
        Dict with task types and difficulties.
    """
    return {
        "task_types": [t.value for t in TaskType],
        "difficulties": [d.value for d in TaskDifficulty],
    }
