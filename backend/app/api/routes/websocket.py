"""WebSocket support for real-time scraper updates."""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])

# Store active WebSocket connections by episode_id
_active_connections: dict[str, list[WebSocket]] = {}


class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, episode_id: str):
        """Connect a new WebSocket client."""
        await websocket.accept()
        if episode_id not in self.active_connections:
            self.active_connections[episode_id] = []
        self.active_connections[episode_id].append(websocket)
        logger.info(f"WebSocket connected for episode {episode_id}")

    def disconnect(self, websocket: WebSocket, episode_id: str):
        """Disconnect a WebSocket client."""
        if episode_id in self.active_connections:
            if websocket in self.active_connections[episode_id]:
                self.active_connections[episode_id].remove(websocket)
            if not self.active_connections[episode_id]:
                del self.active_connections[episode_id]
        logger.info(f"WebSocket disconnected for episode {episode_id}")

    async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket):
        """Send a message to a specific client."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast(self, message: dict[str, Any], episode_id: str):
        """Broadcast a message to all clients watching an episode."""
        if episode_id not in self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections[episode_id]:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_json(message)
                else:
                    disconnected.append(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn, episode_id)

    async def send_progress_update(
        self,
        episode_id: str,
        step: int,
        action_type: str,
        reward: float,
        progress: float,
        message: str | None = None,
    ):
        """Send a progress update for an episode."""
        update = {
            "type": "progress",
            "episode_id": episode_id,
            "step": step,
            "action_type": action_type,
            "reward": reward,
            "progress": progress,
            "message": message,
            "timestamp": asyncio.get_event_loop().time(),
        }
        await self.broadcast(update, episode_id)

    async def send_error(self, episode_id: str, error: str, details: dict[str, Any] | None = None):
        """Send an error message."""
        message = {
            "type": "error",
            "episode_id": episode_id,
            "error": error,
            "details": details or {},
            "timestamp": asyncio.get_event_loop().time(),
        }
        await self.broadcast(message, episode_id)

    async def send_completion(
        self,
        episode_id: str,
        success: bool,
        total_reward: float,
        extracted_data: dict[str, Any],
    ):
        """Send a completion notification."""
        message = {
            "type": "completion",
            "episode_id": episode_id,
            "success": success,
            "total_reward": total_reward,
            "extracted_data": extracted_data,
            "timestamp": asyncio.get_event_loop().time(),
        }
        await self.broadcast(message, episode_id)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/episode/{episode_id}")
async def websocket_episode(websocket: WebSocket, episode_id: str):
    """
    WebSocket endpoint for receiving real-time updates about an episode.
    
    Clients can connect to this endpoint to receive updates about:
    - Action execution progress
    - Reward changes
    - Extraction progress
    - Errors
    - Episode completion
    
    Args:
        websocket: WebSocket connection
        episode_id: ID of the episode to watch
    """
    await manager.connect(websocket, episode_id)
    
    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            {
                "type": "connected",
                "episode_id": episode_id,
                "message": f"Connected to episode {episode_id}",
            },
            websocket,
        )
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive messages from client (e.g., subscription updates)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,  # 30 second timeout
                )
                
                try:
                    message = json.loads(data)
                    
                    # Handle ping/pong for keep-alive
                    if message.get("type") == "ping":
                        await manager.send_personal_message(
                            {"type": "pong", "timestamp": asyncio.get_event_loop().time()},
                            websocket,
                        )
                    
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {data}")
                    
            except asyncio.TimeoutError:
                # Send a ping to check if client is still connected
                try:
                    await manager.send_personal_message(
                        {"type": "ping", "timestamp": asyncio.get_event_loop().time()},
                        websocket,
                    )
                except Exception:
                    # Client disconnected
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from episode {episode_id}")
    except Exception as e:
        logger.error(f"WebSocket error for episode {episode_id}: {e}")
    finally:
        manager.disconnect(websocket, episode_id)


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return manager
