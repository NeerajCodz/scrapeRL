"""Shared memory for multi-agent communication and state sharing."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Type alias for async callback functions
MessageCallback = Callable[[Any], Awaitable[None]]


class Message(BaseModel):
    """A message published to a channel."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    channel: str
    payload: Any
    sender: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class Subscription(BaseModel):
    """A subscription to a channel."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    channel: str
    subscriber_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"arbitrary_types_allowed": True}


class Channel:
    """A named channel for pub/sub communication."""

    def __init__(self, name: str, max_history: int = 100) -> None:
        """
        Initialize a channel.

        Args:
            name: Channel name.
            max_history: Maximum number of messages to retain in history.
        """
        self.name = name
        self.max_history = max_history
        self._subscribers: dict[str, MessageCallback] = {}
        self._history: list[Message] = []
        self._lock = asyncio.Lock()

    @property
    def subscriber_count(self) -> int:
        """Get the number of subscribers."""
        return len(self._subscribers)

    async def publish(self, message: Message) -> int:
        """
        Publish a message to all subscribers.

        Args:
            message: Message to publish.

        Returns:
            Number of subscribers that received the message.
        """
        async with self._lock:
            # Add to history
            self._history.append(message)
            if len(self._history) > self.max_history:
                self._history = self._history[-self.max_history:]

            # Notify subscribers
            notified = 0
            for sub_id, callback in list(self._subscribers.items()):
                try:
                    await callback(message)
                    notified += 1
                except Exception as e:
                    logger.error(f"Error notifying subscriber {sub_id}: {e}")

            return notified

    async def subscribe(
        self,
        subscriber_id: str,
        callback: MessageCallback,
    ) -> Subscription:
        """
        Subscribe to the channel.

        Args:
            subscriber_id: Unique identifier for the subscriber.
            callback: Async callback function to receive messages.

        Returns:
            Subscription object.
        """
        async with self._lock:
            self._subscribers[subscriber_id] = callback
            return Subscription(
                channel=self.name,
                subscriber_id=subscriber_id,
            )

    async def unsubscribe(self, subscriber_id: str) -> bool:
        """
        Unsubscribe from the channel.

        Args:
            subscriber_id: Subscriber to remove.

        Returns:
            True if subscriber was found and removed.
        """
        async with self._lock:
            if subscriber_id in self._subscribers:
                del self._subscribers[subscriber_id]
                return True
            return False

    async def get_history(
        self,
        limit: int | None = None,
        since: datetime | None = None,
    ) -> list[Message]:
        """
        Get channel message history.

        Args:
            limit: Maximum number of messages to return.
            since: Only return messages after this timestamp.

        Returns:
            List of historical messages.
        """
        async with self._lock:
            messages = self._history

            if since:
                messages = [m for m in messages if m.timestamp > since]

            if limit:
                messages = messages[-limit:]

            return messages

    async def clear_history(self) -> int:
        """
        Clear the channel's message history.

        Returns:
            Number of messages cleared.
        """
        async with self._lock:
            count = len(self._history)
            self._history.clear()
            return count


class SharedMemory:
    """
    Thread-safe shared memory for multi-agent coordination.

    This memory layer provides pub/sub messaging and shared state storage
    for coordination between multiple agents. All operations are thread-safe.

    Attributes:
        _channels: Dictionary of channels by name.
        _state: Shared key-value state store.
    """

    def __init__(self, max_channel_history: int = 100) -> None:
        """
        Initialize shared memory.

        Args:
            max_channel_history: Maximum history per channel.
        """
        self.max_channel_history = max_channel_history
        self._channels: dict[str, Channel] = {}
        self._state: dict[str, Any] = {}
        self._state_lock = asyncio.Lock()
        self._channel_lock = asyncio.Lock()
        self._queues: dict[str, dict[str, asyncio.Queue]] = defaultdict(dict)

    async def get_channel(self, name: str) -> Channel:
        """
        Get or create a channel by name.

        Args:
            name: Channel name.

        Returns:
            The channel object.
        """
        async with self._channel_lock:
            if name not in self._channels:
                self._channels[name] = Channel(
                    name=name,
                    max_history=self.max_channel_history,
                )
            return self._channels[name]

    async def publish(
        self,
        channel: str,
        payload: Any,
        sender: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """
        Publish a message to a channel.

        Args:
            channel: Channel name to publish to.
            payload: Message payload.
            sender: Optional sender identifier.
            metadata: Optional message metadata.

        Returns:
            The published message.
        """
        ch = await self.get_channel(channel)

        message = Message(
            channel=channel,
            payload=payload,
            sender=sender,
            metadata=metadata or {},
        )

        await ch.publish(message)

        # Also put in subscriber queues
        async with self._channel_lock:
            if channel in self._queues:
                for queue in self._queues[channel].values():
                    try:
                        queue.put_nowait(message)
                    except asyncio.QueueFull:
                        # Remove oldest and add new
                        try:
                            queue.get_nowait()
                            queue.put_nowait(message)
                        except asyncio.QueueEmpty:
                            pass

        return message

    async def subscribe(
        self,
        channel: str,
        subscriber_id: str,
        callback: MessageCallback,
    ) -> Subscription:
        """
        Subscribe to a channel with a callback.

        Args:
            channel: Channel name to subscribe to.
            subscriber_id: Unique subscriber identifier.
            callback: Async callback for received messages.

        Returns:
            Subscription object.
        """
        ch = await self.get_channel(channel)
        return await ch.subscribe(subscriber_id, callback)

    async def subscribe_queue(
        self,
        channel: str,
        subscriber_id: str,
        max_size: int = 100,
    ) -> asyncio.Queue[Message]:
        """
        Subscribe to a channel and receive messages via a queue.

        This is an alternative to callback-based subscriptions.

        Args:
            channel: Channel name to subscribe to.
            subscriber_id: Unique subscriber identifier.
            max_size: Maximum queue size.

        Returns:
            Queue that will receive messages.
        """
        async with self._channel_lock:
            if subscriber_id not in self._queues[channel]:
                self._queues[channel][subscriber_id] = asyncio.Queue(maxsize=max_size)
            return self._queues[channel][subscriber_id]

    async def unsubscribe(self, channel: str, subscriber_id: str) -> bool:
        """
        Unsubscribe from a channel.

        Args:
            channel: Channel name.
            subscriber_id: Subscriber to remove.

        Returns:
            True if subscriber was found and removed.
        """
        async with self._channel_lock:
            # Remove from callback subscriptions
            if channel in self._channels:
                await self._channels[channel].unsubscribe(subscriber_id)

            # Remove from queue subscriptions
            if channel in self._queues and subscriber_id in self._queues[channel]:
                del self._queues[channel][subscriber_id]
                return True

            return False

    async def set_state(self, key: str, value: Any) -> None:
        """
        Set a shared state value.

        Args:
            key: State key.
            value: Value to store.
        """
        async with self._state_lock:
            self._state[key] = value

    async def get_state(self, key: str, default: Any = None) -> Any:
        """
        Get a shared state value.

        Args:
            key: State key.
            default: Default value if key not found.

        Returns:
            The stored value or default.
        """
        async with self._state_lock:
            return self._state.get(key, default)

    async def delete_state(self, key: str) -> bool:
        """
        Delete a shared state value.

        Args:
            key: State key to delete.

        Returns:
            True if key was found and deleted.
        """
        async with self._state_lock:
            if key in self._state:
                del self._state[key]
                return True
            return False

    async def update_state(self, key: str, updater: Callable[[Any], Any]) -> Any:
        """
        Atomically update a state value.

        Args:
            key: State key.
            updater: Function that takes current value and returns new value.

        Returns:
            The new value after update.
        """
        async with self._state_lock:
            current = self._state.get(key)
            new_value = updater(current)
            self._state[key] = new_value
            return new_value

    async def get_all_state(self) -> dict[str, Any]:
        """
        Get all shared state values.

        Returns:
            Copy of the state dictionary.
        """
        async with self._state_lock:
            return dict(self._state)

    async def clear_state(self) -> int:
        """
        Clear all shared state.

        Returns:
            Number of keys cleared.
        """
        async with self._state_lock:
            count = len(self._state)
            self._state.clear()
            return count

    async def list_channels(self) -> list[str]:
        """
        List all active channels.

        Returns:
            List of channel names.
        """
        async with self._channel_lock:
            return list(self._channels.keys())

    async def delete_channel(self, name: str) -> bool:
        """
        Delete a channel and all its subscriptions.

        Args:
            name: Channel name to delete.

        Returns:
            True if channel was found and deleted.
        """
        async with self._channel_lock:
            if name in self._channels:
                del self._channels[name]
                if name in self._queues:
                    del self._queues[name]
                return True
            return False

    async def clear(self) -> dict[str, int]:
        """
        Clear all channels and state.

        Returns:
            Dictionary with counts of cleared items.
        """
        async with self._channel_lock:
            channel_count = len(self._channels)
            self._channels.clear()
            self._queues.clear()

        async with self._state_lock:
            state_count = len(self._state)
            self._state.clear()

        return {
            "channels": channel_count,
            "state_keys": state_count,
        }

    async def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about shared memory.

        Returns:
            Dictionary with memory statistics.
        """
        async with self._channel_lock:
            channel_stats = {}
            for name, channel in self._channels.items():
                channel_stats[name] = {
                    "subscribers": channel.subscriber_count,
                    "history_size": len(channel._history),
                }

        async with self._state_lock:
            state_keys = list(self._state.keys())

        return {
            "channel_count": len(channel_stats),
            "channels": channel_stats,
            "state_key_count": len(state_keys),
            "state_keys": state_keys,
            "max_channel_history": self.max_channel_history,
        }
