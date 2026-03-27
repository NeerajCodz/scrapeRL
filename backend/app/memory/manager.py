"""Unified memory manager providing access to all memory layers."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings
from app.memory.long_term import Document, LongTermMemory, SearchResult
from app.memory.shared import Message, SharedMemory
from app.memory.short_term import MemoryEntry, ShortTermMemory
from app.memory.working import WorkingMemory, WorkingMemoryItem

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memory layers."""

    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"
    SHARED = "shared"


class MemoryStats(BaseModel):
    """Statistics for all memory layers."""

    short_term: dict[str, Any] = Field(default_factory=dict)
    working: dict[str, Any] = Field(default_factory=dict)
    long_term: dict[str, Any] = Field(default_factory=dict)
    shared: dict[str, Any] = Field(default_factory=dict)


class MemoryManager:
    """
    Unified interface to all memory layers.

    The MemoryManager provides a single entry point for interacting with
    different types of memory (short-term, working, long-term, shared).
    It handles initialization, coordination, and lifecycle management.

    Attributes:
        short_term: Episode-scoped dictionary memory.
        working: LRU-based reasoning scratch space.
        long_term: Persistent vector storage.
        shared: Multi-agent shared state.
    """

    def __init__(self, settings: Settings) -> None:
        """
        Initialize memory manager with settings.

        Args:
            settings: Application settings.
        """
        self._settings = settings
        self._initialized = False

        # Initialize memory layers
        self.short_term = ShortTermMemory(
            max_size=settings.short_term_memory_size,
        )

        self.working = WorkingMemory(
            capacity=settings.working_memory_size,
        )

        self.long_term = LongTermMemory(
            collection_name=settings.chroma_collection_name,
            persist_directory=settings.chroma_persist_directory,
            top_k=settings.long_term_memory_top_k,
        )

        self.shared = SharedMemory()

    async def initialize(self) -> None:
        """
        Initialize all memory layers.

        This should be called during application startup.
        """
        if self._initialized:
            return

        try:
            # Initialize long-term memory (ChromaDB)
            await self.long_term.initialize()
            self._initialized = True
            logger.info("Memory manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize memory manager: {e}")
            raise

    async def shutdown(self) -> None:
        """
        Shutdown all memory layers gracefully.

        This should be called during application shutdown.
        """
        try:
            # Persist long-term memory
            await self.long_term.shutdown()

            # Clear working memory
            await self.working.clear()

            self._initialized = False
            logger.info("Memory manager shutdown complete")
        except Exception as e:
            logger.error(f"Error during memory manager shutdown: {e}")
            raise

    @property
    def is_initialized(self) -> bool:
        """Check if memory manager is initialized."""
        return self._initialized

    # =========================================================================
    # Unified Store Interface
    # =========================================================================

    async def store(
        self,
        key: str,
        value: Any,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        **kwargs: Any,
    ) -> Any:
        """
        Store a value in the specified memory layer.

        Args:
            key: Key or identifier for the stored value.
            value: Value to store.
            memory_type: Which memory layer to use.
            **kwargs: Additional arguments passed to the specific layer.

        Returns:
            The created entry/document (varies by memory type).

        Raises:
            ValueError: If memory_type is invalid.
        """
        match memory_type:
            case MemoryType.SHORT_TERM:
                tags = kwargs.get("tags")
                return await self.short_term.set(key, value, tags=tags)

            case MemoryType.WORKING:
                priority = kwargs.get("priority", 0.0)
                metadata = kwargs.get("metadata")
                return await self.working.push(
                    content=value,
                    item_id=key,
                    priority=priority,
                    metadata=metadata,
                )

            case MemoryType.LONG_TERM:
                if not isinstance(value, str):
                    value = str(value)
                metadata = kwargs.get("metadata")
                embedding = kwargs.get("embedding")
                return await self.long_term.store(
                    content=value,
                    document_id=key,
                    metadata=metadata,
                    embedding=embedding,
                )

            case MemoryType.SHARED:
                await self.shared.set_state(key, value)
                return value

            case _:
                raise ValueError(f"Invalid memory type: {memory_type}")

    # =========================================================================
    # Unified Retrieve Interface
    # =========================================================================

    async def retrieve(
        self,
        key: str,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        default: Any = None,
    ) -> Any:
        """
        Retrieve a value from the specified memory layer.

        Args:
            key: Key or identifier to look up.
            memory_type: Which memory layer to query.
            default: Default value if not found.

        Returns:
            The stored value or default.

        Raises:
            ValueError: If memory_type is invalid.
        """
        match memory_type:
            case MemoryType.SHORT_TERM:
                return await self.short_term.get(key, default=default)

            case MemoryType.WORKING:
                item = await self.working.peek_by_id(key)
                return item.content if item else default

            case MemoryType.LONG_TERM:
                doc = await self.long_term.get(key)
                return doc.content if doc else default

            case MemoryType.SHARED:
                return await self.shared.get_state(key, default=default)

            case _:
                raise ValueError(f"Invalid memory type: {memory_type}")

    # =========================================================================
    # Unified Search Interface
    # =========================================================================

    async def search(
        self,
        query: str,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        top_k: int = 10,
        **kwargs: Any,
    ) -> list[Any]:
        """
        Search for values in the specified memory layer.

        Args:
            query: Search query.
            memory_type: Which memory layer to search.
            top_k: Maximum number of results.
            **kwargs: Additional arguments for specific layers.

        Returns:
            List of matching entries/documents.

        Raises:
            ValueError: If memory_type is invalid or doesn't support search.
        """
        match memory_type:
            case MemoryType.SHORT_TERM:
                # Search by tag or return all keys containing query
                tag = kwargs.get("tag")
                if tag:
                    return list((await self.short_term.get_by_tag(tag)).items())[:top_k]
                keys = await self.short_term.list_keys()
                matching = [k for k in keys if query.lower() in k.lower()]
                results = []
                for key in matching[:top_k]:
                    value = await self.short_term.get(key)
                    results.append((key, value))
                return results

            case MemoryType.WORKING:
                # Search working memory items
                def matches(item: WorkingMemoryItem) -> bool:
                    content_str = str(item.content).lower()
                    return query.lower() in content_str

                items = await self.working.search(matches)
                return items[:top_k]

            case MemoryType.LONG_TERM:
                where = kwargs.get("where")
                query_embedding = kwargs.get("query_embedding")
                return await self.long_term.search(
                    query=query,
                    top_k=top_k,
                    where=where,
                    query_embedding=query_embedding,
                )

            case MemoryType.SHARED:
                # Search state keys
                all_state = await self.shared.get_all_state()
                matching = [
                    (k, v)
                    for k, v in all_state.items()
                    if query.lower() in k.lower()
                    or query.lower() in str(v).lower()
                ]
                return matching[:top_k]

            case _:
                raise ValueError(f"Invalid memory type: {memory_type}")

    # =========================================================================
    # Unified Clear Interface
    # =========================================================================

    async def clear(
        self,
        memory_type: MemoryType | None = None,
    ) -> dict[str, int]:
        """
        Clear memory layers.

        Args:
            memory_type: Specific layer to clear, or None for all.

        Returns:
            Dictionary with counts of cleared items per layer.
        """
        results: dict[str, int] = {}

        if memory_type is None or memory_type == MemoryType.SHORT_TERM:
            results["short_term"] = await self.short_term.clear()

        if memory_type is None or memory_type == MemoryType.WORKING:
            results["working"] = await self.working.clear()

        if memory_type is None or memory_type == MemoryType.LONG_TERM:
            results["long_term"] = await self.long_term.clear()

        if memory_type is None or memory_type == MemoryType.SHARED:
            shared_results = await self.shared.clear()
            results["shared_channels"] = shared_results["channels"]
            results["shared_state"] = shared_results["state_keys"]

        return results

    # =========================================================================
    # Episode Management
    # =========================================================================

    async def start_episode(self, episode_id: str) -> None:
        """
        Start a new episode, clearing episode-scoped memory.

        Args:
            episode_id: Unique identifier for the episode.
        """
        await self.short_term.set_episode(episode_id)
        await self.working.clear()
        logger.debug(f"Started episode: {episode_id}")

    async def end_episode(self) -> dict[str, int]:
        """
        End the current episode, clearing temporary memory.

        Returns:
            Counts of cleared items.
        """
        results = {
            "short_term": await self.short_term.clear(),
            "working": await self.working.clear(),
        }
        logger.debug(f"Ended episode: {results}")
        return results

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> MemoryStats:
        """
        Get statistics from all memory layers.

        Returns:
            MemoryStats with info from each layer.
        """
        return MemoryStats(
            short_term=await self.short_term.get_stats(),
            working=await self.working.get_stats(),
            long_term=await self.long_term.get_stats(),
            shared=await self.shared.get_stats(),
        )

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    async def remember(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        """
        Store content in long-term memory for later retrieval.

        This is a convenience method for storing knowledge.

        Args:
            content: Text content to remember.
            metadata: Optional metadata.

        Returns:
            The stored document.
        """
        return await self.long_term.store(content=content, metadata=metadata)

    async def recall(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Recall relevant memories based on a query.

        This is a convenience method for semantic search.

        Args:
            query: Search query.
            top_k: Number of results to return.

        Returns:
            List of relevant search results.
        """
        return await self.long_term.search(query=query, top_k=top_k)

    async def think(
        self,
        thought: str,
        priority: float = 0.0,
    ) -> WorkingMemoryItem:
        """
        Add a thought to working memory.

        This is a convenience method for reasoning steps.

        Args:
            thought: The thought content.
            priority: Priority score.

        Returns:
            The working memory item.
        """
        return await self.working.push(content=thought, priority=priority)

    async def broadcast(
        self,
        channel: str,
        message: Any,
        sender: str | None = None,
    ) -> Message:
        """
        Broadcast a message to a shared channel.

        This is a convenience method for multi-agent communication.

        Args:
            channel: Channel name.
            message: Message payload.
            sender: Optional sender identifier.

        Returns:
            The published message.
        """
        return await self.shared.publish(
            channel=channel,
            payload=message,
            sender=sender,
        )
