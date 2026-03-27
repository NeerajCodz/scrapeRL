"""Working memory for reasoning and scratch space with LRU eviction."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkingMemoryItem(BaseModel):
    """A single item in working memory."""

    id: str
    content: Any
    priority: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class WorkingMemory:
    """
    Working memory for reasoning and scratch computations.

    This memory layer provides a limited-capacity buffer with LRU (Least Recently Used)
    eviction policy. It's designed for temporary reasoning steps, intermediate results,
    and scratch space during agent deliberation.

    Attributes:
        capacity: Maximum number of items in working memory.
        _items: Internal LRU-ordered storage.
    """

    def __init__(self, capacity: int = 20) -> None:
        """
        Initialize working memory.

        Args:
            capacity: Maximum number of items to store. Defaults to 20.
        """
        self.capacity = capacity
        self._items: OrderedDict[str, WorkingMemoryItem] = OrderedDict()
        self._counter = 0
        self._lock = asyncio.Lock()

    @property
    def size(self) -> int:
        """Get current number of items in memory."""
        return len(self._items)

    @property
    def is_full(self) -> bool:
        """Check if memory is at capacity."""
        return len(self._items) >= self.capacity

    async def push(
        self,
        content: Any,
        item_id: str | None = None,
        priority: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> WorkingMemoryItem:
        """
        Push a new item into working memory.

        If capacity is reached, the least recently used item is evicted.

        Args:
            content: The content to store.
            item_id: Optional custom ID. Auto-generated if not provided.
            priority: Priority score for potential prioritized eviction.
            metadata: Optional metadata dictionary.

        Returns:
            The created working memory item.
        """
        async with self._lock:
            # Generate ID if not provided
            if item_id is None:
                self._counter += 1
                item_id = f"wm_{self._counter}"

            now = datetime.utcnow()

            # Check if item already exists (update it)
            if item_id in self._items:
                item = self._items[item_id]
                item.content = content
                item.last_accessed = now
                item.access_count += 1
                if metadata:
                    item.metadata.update(metadata)
                if priority != 0.0:
                    item.priority = priority
                # Move to end (most recent)
                self._items.move_to_end(item_id)
                return item

            # Evict LRU item if at capacity
            if len(self._items) >= self.capacity:
                self._evict_lru()

            # Create new item
            item = WorkingMemoryItem(
                id=item_id,
                content=content,
                priority=priority,
                created_at=now,
                last_accessed=now,
                metadata=metadata or {},
            )
            self._items[item_id] = item
            return item

    def _evict_lru(self) -> WorkingMemoryItem | None:
        """
        Evict the least recently used item.

        Returns:
            The evicted item, or None if memory was empty.
        """
        if not self._items:
            return None
        # Pop first item (least recently used)
        _, item = self._items.popitem(last=False)
        return item

    async def pop(self) -> WorkingMemoryItem | None:
        """
        Remove and return the most recently used item.

        Returns:
            The most recent item, or None if memory is empty.
        """
        async with self._lock:
            if not self._items:
                return None
            _, item = self._items.popitem(last=True)
            return item

    async def pop_by_id(self, item_id: str) -> WorkingMemoryItem | None:
        """
        Remove and return an item by its ID.

        Args:
            item_id: The ID of the item to remove.

        Returns:
            The removed item, or None if not found.
        """
        async with self._lock:
            return self._items.pop(item_id, None)

    async def peek(self) -> WorkingMemoryItem | None:
        """
        Return the most recently used item without removing it.

        Returns:
            The most recent item, or None if memory is empty.
        """
        async with self._lock:
            if not self._items:
                return None
            # Get last item
            item_id = next(reversed(self._items))
            item = self._items[item_id]
            item.last_accessed = datetime.utcnow()
            item.access_count += 1
            return item

    async def peek_by_id(self, item_id: str) -> WorkingMemoryItem | None:
        """
        Return an item by ID without removing it.

        Args:
            item_id: The ID of the item to peek.

        Returns:
            The item, or None if not found.
        """
        async with self._lock:
            item = self._items.get(item_id)
            if item:
                item.last_accessed = datetime.utcnow()
                item.access_count += 1
                # Move to end (mark as recently accessed)
                self._items.move_to_end(item_id)
            return item

    async def get_all(self) -> list[WorkingMemoryItem]:
        """
        Get all items in memory, ordered by recency.

        Returns:
            List of items from least to most recent.
        """
        async with self._lock:
            return list(self._items.values())

    async def get_recent(self, n: int = 5) -> list[WorkingMemoryItem]:
        """
        Get the N most recently accessed items.

        Args:
            n: Number of items to return.

        Returns:
            List of most recent items.
        """
        async with self._lock:
            items = list(self._items.values())
            return items[-n:] if n < len(items) else items

    async def clear(self) -> int:
        """
        Clear all items from working memory.

        Returns:
            Number of items that were cleared.
        """
        async with self._lock:
            count = len(self._items)
            self._items.clear()
            self._counter = 0
            return count

    async def search(self, predicate: Any) -> list[WorkingMemoryItem]:
        """
        Search items using a predicate function.

        Args:
            predicate: Callable that takes a WorkingMemoryItem and returns bool.

        Returns:
            List of matching items.
        """
        async with self._lock:
            return [item for item in self._items.values() if predicate(item)]

    async def update_priority(self, item_id: str, priority: float) -> bool:
        """
        Update the priority of an item.

        Args:
            item_id: ID of the item to update.
            priority: New priority value.

        Returns:
            True if item was found and updated, False otherwise.
        """
        async with self._lock:
            if item_id in self._items:
                self._items[item_id].priority = priority
                return True
            return False

    async def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about working memory.

        Returns:
            Dictionary with memory statistics.
        """
        async with self._lock:
            return {
                "size": len(self._items),
                "capacity": self.capacity,
                "is_full": len(self._items) >= self.capacity,
                "utilization": len(self._items) / self.capacity if self.capacity > 0 else 0,
                "item_ids": list(self._items.keys()),
            }
