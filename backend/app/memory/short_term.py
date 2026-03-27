"""Short-term memory for episode-scoped data storage."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MemoryEntry(BaseModel, Generic[T]):
    """A single memory entry with metadata."""

    key: str
    value: Any
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = 0
    tags: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


class ShortTermMemory:
    """
    Episode-scoped memory using dictionary-based storage.

    This memory layer is designed for transient data that should persist
    only within a single episode. It automatically clears when the episode
    resets.

    Attributes:
        max_size: Maximum number of entries allowed.
        _store: Internal storage dictionary.
        _episode_id: Current episode identifier.
    """

    def __init__(self, max_size: int = 100) -> None:
        """
        Initialize short-term memory.

        Args:
            max_size: Maximum number of entries to store. Defaults to 100.
        """
        self.max_size = max_size
        self._store: OrderedDict[str, MemoryEntry] = OrderedDict()
        self._episode_id: str | None = None
        self._lock = asyncio.Lock()

    @property
    def episode_id(self) -> str | None:
        """Get the current episode ID."""
        return self._episode_id

    @property
    def size(self) -> int:
        """Get the current number of entries."""
        return len(self._store)

    async def set_episode(self, episode_id: str) -> None:
        """
        Set the current episode ID and clear existing memory.

        Args:
            episode_id: Unique identifier for the new episode.
        """
        async with self._lock:
            if self._episode_id != episode_id:
                self._store.clear()
                self._episode_id = episode_id

    async def set(
        self,
        key: str,
        value: Any,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        """
        Store a value in short-term memory.

        Args:
            key: Unique key for the entry.
            value: Value to store.
            tags: Optional tags for categorization.

        Returns:
            The created or updated memory entry.

        Raises:
            ValueError: If max_size would be exceeded for a new key.
        """
        async with self._lock:
            now = datetime.utcnow()

            if key in self._store:
                entry = self._store[key]
                entry.value = value
                entry.updated_at = now
                if tags is not None:
                    entry.tags = tags
                # Move to end (most recent)
                self._store.move_to_end(key)
            else:
                # Check capacity
                if len(self._store) >= self.max_size:
                    # Remove oldest entry
                    self._store.popitem(last=False)

                entry = MemoryEntry(
                    key=key,
                    value=value,
                    created_at=now,
                    updated_at=now,
                    tags=tags or [],
                )
                self._store[key] = entry

            return entry

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from short-term memory.

        Args:
            key: Key to look up.
            default: Default value if key not found.

        Returns:
            The stored value or default.
        """
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return default
            entry.access_count += 1
            return entry.value

    async def get_entry(self, key: str) -> MemoryEntry | None:
        """
        Retrieve a full memory entry with metadata.

        Args:
            key: Key to look up.

        Returns:
            The memory entry or None if not found.
        """
        async with self._lock:
            entry = self._store.get(key)
            if entry:
                entry.access_count += 1
            return entry

    async def delete(self, key: str) -> bool:
        """
        Delete an entry from memory.

        Args:
            key: Key to delete.

        Returns:
            True if the key was found and deleted, False otherwise.
        """
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> int:
        """
        Clear all entries from memory.

        Returns:
            Number of entries that were cleared.
        """
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    async def list_keys(self, tag: str | None = None) -> list[str]:
        """
        List all keys in memory, optionally filtered by tag.

        Args:
            tag: Optional tag to filter by.

        Returns:
            List of matching keys.
        """
        async with self._lock:
            if tag is None:
                return list(self._store.keys())
            return [k for k, v in self._store.items() if tag in v.tags]

    async def get_by_tag(self, tag: str) -> dict[str, Any]:
        """
        Retrieve all entries with a specific tag.

        Args:
            tag: Tag to filter by.

        Returns:
            Dictionary of key-value pairs matching the tag.
        """
        async with self._lock:
            return {
                k: v.value for k, v in self._store.items() if tag in v.tags
            }

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in memory.

        Args:
            key: Key to check.

        Returns:
            True if key exists, False otherwise.
        """
        async with self._lock:
            return key in self._store

    async def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the memory store.

        Returns:
            Dictionary with memory statistics.
        """
        async with self._lock:
            return {
                "size": len(self._store),
                "max_size": self.max_size,
                "episode_id": self._episode_id,
                "keys": list(self._store.keys()),
                "utilization": len(self._store) / self.max_size if self.max_size > 0 else 0,
            }
