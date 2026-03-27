"""Memory agent for memory operations and knowledge management."""

from datetime import datetime, timezone
from typing import Any

from app.core.action import Action, ActionType
from app.core.observation import Observation

from .base import BaseAgent


class MemoryEntry:
    """A single memory entry."""

    def __init__(
        self,
        key: str,
        value: Any,
        memory_type: str = "working",
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Initialize memory entry."""
        self.key = key
        self.value = value
        self.memory_type = memory_type
        self.ttl_seconds = ttl_seconds
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count = 0

    def is_expired(self) -> bool:
        """Check if the memory entry has expired."""
        if self.ttl_seconds is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds

    def access(self) -> Any:
        """Access the memory and update metadata."""
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count += 1
        return self.value

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "memory_type": self.memory_type,
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
        }


class MemoryAgent(BaseAgent):
    """
    Agent responsible for memory operations and knowledge management.
    
    The MemoryAgent handles:
    - Storing and retrieving memories across different layers
    - Managing short-term, working, and long-term memory
    - Memory consolidation and cleanup
    - Relevance-based memory retrieval
    - Sharing knowledge between episodes
    """

    def __init__(
        self,
        agent_id: str = "memory",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the MemoryAgent.
        
        Args:
            agent_id: Unique identifier for this agent.
            config: Optional configuration with keys:
                - max_short_term: Max short-term memory entries (default: 100)
                - max_working: Max working memory entries (default: 50)
                - consolidation_threshold: Accesses before long-term (default: 3)
                - enable_auto_cleanup: Auto cleanup expired entries (default: True)
        """
        super().__init__(agent_id, config)
        self.max_short_term = self.config.get("max_short_term", 100)
        self.max_working = self.config.get("max_working", 50)
        self.consolidation_threshold = self.config.get("consolidation_threshold", 3)
        self.enable_auto_cleanup = self.config.get("enable_auto_cleanup", True)

        # Memory stores
        self._short_term: dict[str, MemoryEntry] = {}
        self._working: dict[str, MemoryEntry] = {}
        self._pending_operations: list[dict[str, Any]] = []

    async def act(self, observation: Observation) -> Action:
        """
        Select the best memory action based on observation.
        
        Analyzes the current state and determines if any memory
        operations are needed.
        
        Args:
            observation: The current state observation.
            
        Returns:
            The memory action to execute.
        """
        try:
            # Process any pending messages requesting memory operations
            messages = self.get_pending_messages()
            for msg in messages:
                if msg.get("message_type") == "memory_request":
                    return self._process_memory_request(msg)

            # Auto cleanup if enabled
            if self.enable_auto_cleanup:
                self._cleanup_expired()

            # Check if we should store new information
            store_action = self._check_for_storage(observation)
            if store_action:
                return store_action

            # Check if any memories need consolidation
            consolidation_action = self._check_for_consolidation()
            if consolidation_action:
                return consolidation_action

            # No memory operations needed
            return Action(
                action_type=ActionType.WAIT,
                parameters={"duration_ms": 100},
                reasoning="No memory operations required",
                confidence=1.0,
                agent_id=self.agent_id,
            )

        except Exception as e:
            return Action(
                action_type=ActionType.FAIL,
                parameters={"success": False, "message": str(e)},
                reasoning=f"Memory operation error: {e}",
                confidence=1.0,
                agent_id=self.agent_id,
            )

    async def plan(self, observation: Observation) -> list[Action]:
        """
        Create a plan of memory operations.
        
        Plans memory operations needed based on the current state
        and extracted data.
        
        Args:
            observation: The current state observation.
            
        Returns:
            A list of planned memory actions.
        """
        try:
            actions: list[Action] = []

            # Plan to store extracted fields
            for field in observation.extracted_so_far:
                if field.verified and field.confidence > 0.8:
                    actions.append(
                        Action(
                            action_type=ActionType.STORE_MEMORY,
                            parameters={
                                "key": f"extracted:{field.field_name}",
                                "value": field.value,
                                "memory_type": "working",
                                "metadata": {
                                    "source": observation.current_url,
                                    "confidence": field.confidence,
                                },
                            },
                            reasoning=f"Storing verified field: {field.field_name}",
                            confidence=0.9,
                            agent_id=self.agent_id,
                        )
                    )

            # Plan to recall relevant memories for current task
            if observation.task_context:
                for target in observation.task_context.target_fields:
                    actions.append(
                        Action(
                            action_type=ActionType.RECALL_MEMORY,
                            parameters={
                                "key": f"pattern:{target}",
                                "memory_type": "long_term",
                            },
                            reasoning=f"Recalling patterns for field: {target}",
                            confidence=0.7,
                            agent_id=self.agent_id,
                        )
                    )

            return actions

        except Exception as e:
            return [
                Action(
                    action_type=ActionType.FAIL,
                    parameters={"message": f"Memory planning failed: {e}"},
                    reasoning=str(e),
                    confidence=1.0,
                    agent_id=self.agent_id,
                )
            ]

    def store(
        self,
        key: str,
        value: Any,
        memory_type: str = "working",
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Store a value in memory.
        
        Args:
            key: The key to store under.
            value: The value to store.
            memory_type: Type of memory (short_term, working).
            ttl_seconds: Optional time-to-live.
            metadata: Optional metadata.
            
        Returns:
            True if stored successfully.
        """
        entry = MemoryEntry(
            key=key,
            value=value,
            memory_type=memory_type,
            ttl_seconds=ttl_seconds,
            metadata=metadata,
        )

        if memory_type == "short_term":
            self._enforce_limit(self._short_term, self.max_short_term)
            self._short_term[key] = entry
        elif memory_type == "working":
            self._enforce_limit(self._working, self.max_working)
            self._working[key] = entry
        else:
            return False

        return True

    def recall(
        self,
        key: str,
        memory_type: str | None = None,
    ) -> Any | None:
        """
        Recall a value from memory.
        
        Args:
            key: The key to recall.
            memory_type: Optional specific memory type to search.
            
        Returns:
            The value if found, None otherwise.
        """
        # Search in order of specificity
        stores = []
        if memory_type == "working" or memory_type is None:
            stores.append(self._working)
        if memory_type == "short_term" or memory_type is None:
            stores.append(self._short_term)

        for store in stores:
            if key in store:
                entry = store[key]
                if not entry.is_expired():
                    return entry.access()
                else:
                    # Clean up expired entry
                    del store[key]

        return None

    def search(
        self,
        query: str,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search memories by key prefix or content.
        
        Args:
            query: Search query (matches key prefix).
            memory_type: Optional specific memory type.
            limit: Maximum results to return.
            
        Returns:
            List of matching memories.
        """
        results: list[dict[str, Any]] = []
        query_lower = query.lower()

        stores = []
        if memory_type in ("working", None):
            stores.append(("working", self._working))
        if memory_type in ("short_term", None):
            stores.append(("short_term", self._short_term))

        for store_name, store in stores:
            for key, entry in store.items():
                if entry.is_expired():
                    continue

                # Match by key prefix or value content
                if (
                    key.lower().startswith(query_lower)
                    or query_lower in str(entry.value).lower()
                ):
                    results.append({
                        **entry.to_dict(),
                        "store": store_name,
                    })

                if len(results) >= limit:
                    break

        return results[:limit]

    def _process_memory_request(self, message: dict[str, Any]) -> Action:
        """Process a memory request from another agent."""
        content = message.get("content", {})
        operation = content.get("operation", "recall")
        key = content.get("key", "")

        if operation == "store":
            success = self.store(
                key=key,
                value=content.get("value"),
                memory_type=content.get("memory_type", "working"),
                ttl_seconds=content.get("ttl_seconds"),
                metadata=content.get("metadata"),
            )
            return Action(
                action_type=ActionType.STORE_MEMORY,
                parameters={"key": key, "success": success},
                reasoning=f"Processed store request for key: {key}",
                confidence=1.0 if success else 0.5,
                agent_id=self.agent_id,
            )

        elif operation == "recall":
            value = self.recall(key, content.get("memory_type"))
            return Action(
                action_type=ActionType.RECALL_MEMORY,
                parameters={"key": key, "value": value, "found": value is not None},
                reasoning=f"Processed recall request for key: {key}",
                confidence=1.0 if value else 0.3,
                agent_id=self.agent_id,
            )

        else:
            return Action(
                action_type=ActionType.FAIL,
                parameters={"message": f"Unknown memory operation: {operation}"},
                reasoning=f"Invalid memory request",
                confidence=1.0,
                agent_id=self.agent_id,
            )

    def _check_for_storage(self, observation: Observation) -> Action | None:
        """Check if any new information should be stored."""
        # Store newly extracted, verified fields
        for field in observation.extracted_so_far:
            key = f"field:{field.field_name}"
            if key not in self._working and field.verified:
                return Action(
                    action_type=ActionType.STORE_MEMORY,
                    parameters={
                        "key": key,
                        "value": {
                            "field_name": field.field_name,
                            "value": field.value,
                            "confidence": field.confidence,
                            "source": observation.current_url,
                        },
                        "memory_type": "working",
                    },
                    reasoning=f"Storing verified extraction: {field.field_name}",
                    confidence=0.85,
                    agent_id=self.agent_id,
                )

        return None

    def _check_for_consolidation(self) -> Action | None:
        """Check if any memories should be consolidated to long-term."""
        for key, entry in self._working.items():
            if entry.access_count >= self.consolidation_threshold:
                return Action(
                    action_type=ActionType.STORE_MEMORY,
                    parameters={
                        "key": key,
                        "value": entry.value,
                        "memory_type": "long_term",
                        "metadata": {
                            "access_count": entry.access_count,
                            "consolidated_from": "working",
                        },
                    },
                    reasoning=f"Consolidating frequently accessed memory: {key}",
                    confidence=0.8,
                    agent_id=self.agent_id,
                )

        return None

    def _cleanup_expired(self) -> int:
        """Clean up expired memory entries."""
        cleaned = 0

        for store in [self._short_term, self._working]:
            expired_keys = [
                k for k, v in store.items()
                if v.is_expired()
            ]
            for key in expired_keys:
                del store[key]
                cleaned += 1

        return cleaned

    def _enforce_limit(
        self,
        store: dict[str, MemoryEntry],
        limit: int,
    ) -> None:
        """Enforce memory limit by removing least accessed entries."""
        if len(store) < limit:
            return

        # Sort by access count and last access time
        sorted_entries = sorted(
            store.items(),
            key=lambda x: (x[1].access_count, x[1].accessed_at),
        )

        # Remove oldest/least accessed entries
        to_remove = len(store) - limit + 1
        for key, _ in sorted_entries[:to_remove]:
            del store[key]

    def get_memory_stats(self) -> dict[str, Any]:
        """Get statistics about memory usage."""
        return {
            "short_term_count": len(self._short_term),
            "short_term_limit": self.max_short_term,
            "working_count": len(self._working),
            "working_limit": self.max_working,
            "total_entries": len(self._short_term) + len(self._working),
        }

    def reset(self) -> None:
        """Reset the memory agent state."""
        super().reset()
        self._short_term.clear()
        self._working.clear()
        self._pending_operations.clear()
