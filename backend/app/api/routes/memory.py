"""Memory management endpoints."""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import MemoryManagerDep
from app.memory.manager import MemoryType as ManagerMemoryType

router = APIRouter(prefix="/memory")
logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memory layers."""

    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"
    SHARED = "shared"


class MemoryEntry(BaseModel):
    """A single memory entry."""

    id: str
    memory_type: MemoryType
    content: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    episode_id: str | None = None
    agent_id: str | None = None
    relevance_score: float | None = None
    embedding: list[float] | None = None


class MemoryQueryRequest(BaseModel):
    """Request for querying memory."""

    query: str
    memory_types: list[MemoryType] = Field(default_factory=lambda: list(MemoryType))
    episode_id: str | None = None
    limit: int = 10
    min_relevance: float = 0.0


class MemoryQueryResponse(BaseModel):
    """Response from memory query."""

    entries: list[MemoryEntry]
    total_found: int
    query: str


class MemoryStoreRequest(BaseModel):
    """Request to store a memory entry."""

    memory_type: MemoryType
    content: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    episode_id: str | None = None
    agent_id: str | None = None


class MemoryStats(BaseModel):
    """Statistics about memory usage."""

    short_term_count: int
    working_count: int
    long_term_count: int
    shared_count: int
    total_count: int
    oldest_entry: str | None = None
    newest_entry: str | None = None


# In-memory storage (would use actual memory layers in production)
_memory_store: dict[str, MemoryEntry] = {}


@router.post(
    "/store",
    response_model=MemoryEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Store memory entry",
    description="Store a new memory entry",
)
async def store_memory(request: MemoryStoreRequest) -> MemoryEntry:
    """
    Store a new memory entry.
    
    Args:
        request: Memory storage request.
    
    Returns:
        MemoryEntry: Stored memory entry.
    """
    entry_id = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    entry = MemoryEntry(
        id=entry_id,
        memory_type=request.memory_type,
        content=request.content,
        metadata=request.metadata,
        timestamp=timestamp,
        episode_id=request.episode_id,
        agent_id=request.agent_id,
    )

    _memory_store[entry_id] = entry
    logger.info(f"Stored memory entry {entry_id} ({request.memory_type})")

    return entry


@router.post(
    "/query",
    response_model=MemoryQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query memory",
    description="Query memory entries by semantic similarity or filters",
)
async def query_memory(request: MemoryQueryRequest) -> MemoryQueryResponse:
    """
    Query memory entries.
    
    Args:
        request: Memory query request.
    
    Returns:
        MemoryQueryResponse: Matching memory entries.
    """
    logger.info(f"Querying memory: '{request.query[:50]}...'")

    # Filter entries
    entries = list(_memory_store.values())

    # Filter by memory type
    if request.memory_types:
        entries = [e for e in entries if e.memory_type in request.memory_types]

    # Filter by episode
    if request.episode_id:
        entries = [e for e in entries if e.episode_id == request.episode_id]

    # Simple text matching (would use embeddings in production)
    query_lower = request.query.lower()
    scored_entries = []
    for entry in entries:
        content_str = str(entry.content).lower()
        if query_lower in content_str:
            score = content_str.count(query_lower) / len(content_str.split())
            entry.relevance_score = min(score * 10, 1.0)
            if entry.relevance_score >= request.min_relevance:
                scored_entries.append(entry)

    # Sort by relevance and limit
    scored_entries.sort(key=lambda e: e.relevance_score or 0, reverse=True)
    result_entries = scored_entries[: request.limit]

    return MemoryQueryResponse(
        entries=result_entries,
        total_found=len(scored_entries),
        query=request.query,
    )


@router.get(
    "/{entry_id}",
    response_model=MemoryEntry,
    status_code=status.HTTP_200_OK,
    summary="Get memory entry",
    description="Get a specific memory entry by ID",
)
async def get_memory_entry(entry_id: str) -> MemoryEntry:
    """
    Get a specific memory entry.
    
    Args:
        entry_id: ID of the memory entry.
    
    Returns:
        MemoryEntry: The memory entry.
    """
    if entry_id not in _memory_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory entry {entry_id} not found",
        )
    return _memory_store[entry_id]


@router.put(
    "/{entry_id}",
    response_model=MemoryEntry,
    status_code=status.HTTP_200_OK,
    summary="Update memory entry",
    description="Update an existing memory entry",
)
async def update_memory_entry(
    entry_id: str,
    content: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> MemoryEntry:
    """
    Update a memory entry.
    
    Args:
        entry_id: ID of the entry to update.
        content: New content.
        metadata: Optional new metadata.
    
    Returns:
        MemoryEntry: Updated entry.
    """
    if entry_id not in _memory_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory entry {entry_id} not found",
        )

    entry = _memory_store[entry_id]
    entry.content = content
    if metadata:
        entry.metadata.update(metadata)
    entry.timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(f"Updated memory entry {entry_id}")
    return entry


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete memory entry",
    description="Delete a memory entry",
)
async def delete_memory_entry(entry_id: str) -> None:
    """
    Delete a memory entry.
    
    Args:
        entry_id: ID of the entry to delete.
    """
    if entry_id not in _memory_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory entry {entry_id} not found",
        )

    del _memory_store[entry_id]
    logger.info(f"Deleted memory entry {entry_id}")


@router.get(
    "/stats/overview",
    response_model=MemoryStats,
    status_code=status.HTTP_200_OK,
    summary="Get memory stats",
    description="Get statistics about memory usage",
)
async def get_memory_stats(memory_manager: MemoryManagerDep) -> MemoryStats:
    """
    Get memory statistics.
    
    Returns:
        MemoryStats: Memory usage statistics.
    """
    entries = list(_memory_store.values())

    counts = {mt: 0 for mt in MemoryType}
    for entry in entries:
        counts[entry.memory_type] += 1

    timestamps = [e.timestamp for e in entries]

    manager_stats = await memory_manager.get_stats()
    manager_short_term = int(manager_stats.short_term.get("size", 0))
    manager_working = int(manager_stats.working.get("size", 0))
    manager_long_term = int(manager_stats.long_term.get("document_count", 0))
    manager_shared = int(manager_stats.shared.get("state_key_count", 0))

    short_term_count = counts[MemoryType.SHORT_TERM] + manager_short_term
    working_count = counts[MemoryType.WORKING] + manager_working
    long_term_count = counts[MemoryType.LONG_TERM] + manager_long_term
    shared_count = counts[MemoryType.SHARED] + manager_shared

    return MemoryStats(
        short_term_count=short_term_count,
        working_count=working_count,
        long_term_count=long_term_count,
        shared_count=shared_count,
        total_count=short_term_count + working_count + long_term_count + shared_count,
        oldest_entry=min(timestamps) if timestamps else None,
        newest_entry=max(timestamps) if timestamps else None,
    )


@router.delete(
    "/clear/{memory_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear memory layer",
    description="Clear all entries from a memory layer",
)
async def clear_memory_layer(memory_type: MemoryType, memory_manager: MemoryManagerDep) -> None:
    """
    Clear all entries from a memory layer.
    
    Args:
        memory_type: Type of memory to clear.
    """
    global _memory_store
    to_delete = [k for k, v in _memory_store.items() if v.memory_type == memory_type]
    for key in to_delete:
        del _memory_store[key]
    await memory_manager.clear(memory_type=ManagerMemoryType(memory_type.value))
    logger.info(f"Cleared {len(to_delete)} entries from {memory_type}")


@router.post(
    "/consolidate",
    status_code=status.HTTP_200_OK,
    summary="Consolidate memory",
    description="Consolidate short-term memory into long-term memory",
)
async def consolidate_memory(episode_id: str | None = None) -> dict[str, Any]:
    """
    Consolidate memory from short-term to long-term.
    
    Args:
        episode_id: Optional episode to consolidate.
    
    Returns:
        Consolidation result.
    """
    entries = list(_memory_store.values())

    if episode_id:
        entries = [e for e in entries if e.episode_id == episode_id]

    short_term = [e for e in entries if e.memory_type == MemoryType.SHORT_TERM]

    consolidated = 0
    for entry in short_term:
        entry.memory_type = MemoryType.LONG_TERM
        consolidated += 1

    logger.info(f"Consolidated {consolidated} entries to long-term memory")

    return {
        "consolidated_count": consolidated,
        "episode_id": episode_id,
    }
