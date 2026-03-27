"""Memory module for ScrapeRL agent memory management.

This module provides a multi-layered memory system for RL agents:

- **ShortTermMemory**: Episode-scoped dictionary storage that auto-clears
- **WorkingMemory**: LRU-based reasoning/scratch space with limited capacity
- **LongTermMemory**: Persistent vector storage with ChromaDB for semantic search
- **SharedMemory**: Thread-safe pub/sub and state sharing for multi-agent coordination
- **MemoryManager**: Unified interface to all memory layers

Example:
    >>> from app.config import get_settings
    >>> from app.memory import MemoryManager, MemoryType
    >>>
    >>> settings = get_settings()
    >>> memory = MemoryManager(settings)
    >>> await memory.initialize()
    >>>
    >>> # Store in short-term memory
    >>> await memory.store("key", "value", MemoryType.SHORT_TERM)
    >>>
    >>> # Semantic search in long-term memory
    >>> results = await memory.search("query", MemoryType.LONG_TERM)
    >>>
    >>> # Cleanup
    >>> await memory.shutdown()
"""

from app.memory.long_term import Document, LongTermMemory, SearchResult
from app.memory.manager import MemoryManager, MemoryStats, MemoryType
from app.memory.shared import Channel, Message, SharedMemory, Subscription
from app.memory.short_term import MemoryEntry, ShortTermMemory
from app.memory.working import WorkingMemory, WorkingMemoryItem

__all__ = [
    # Manager
    "MemoryManager",
    "MemoryStats",
    "MemoryType",
    # Short-term
    "ShortTermMemory",
    "MemoryEntry",
    # Working
    "WorkingMemory",
    "WorkingMemoryItem",
    # Long-term
    "LongTermMemory",
    "Document",
    "SearchResult",
    # Shared
    "SharedMemory",
    "Channel",
    "Message",
    "Subscription",
]
