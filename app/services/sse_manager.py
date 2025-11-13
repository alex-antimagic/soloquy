"""
Server-Sent Events (SSE) Connection Manager
Handles real-time message broadcasting for chat conversations
"""
import queue
import time
from typing import Dict, List, Optional, Set
from threading import Lock


class SSEConnectionManager:
    """
    Manages SSE connections for real-time chat updates.

    Tracks connections by conversation identifier and broadcasts events
    to all connected clients in a conversation.
    """

    def __init__(self):
        self.connections: Dict[str, List[Dict]] = {}
        self.online_users: Set[int] = set()  # Track currently online user IDs
        self.user_connections: Dict[int, int] = {}  # Track connection count per user
        self.lock = Lock()

    def register(self, conversation_id: str, user_id: int) -> queue.Queue:
        """
        Register a new SSE connection for a conversation.

        Args:
            conversation_id: Unique identifier for the conversation (e.g., "user_123", "channel_general")
            user_id: ID of the user connecting

        Returns:
            Queue to receive events for this connection
        """
        q = queue.Queue(maxsize=50)  # Limit queue size to prevent memory issues

        with self.lock:
            if conversation_id not in self.connections:
                self.connections[conversation_id] = []

            connection_info = {
                'queue': q,
                'user_id': user_id,
                'connected_at': time.time()
            }
            self.connections[conversation_id].append(connection_info)

            # Track user presence
            was_offline = user_id not in self.online_users
            self.online_users.add(user_id)
            self.user_connections[user_id] = self.user_connections.get(user_id, 0) + 1

        # Broadcast presence update if user just came online
        if was_offline:
            self._broadcast_presence_update(user_id, 'online')

        return q

    def unregister(self, conversation_id: str, q: queue.Queue):
        """
        Unregister an SSE connection when client disconnects.

        Args:
            conversation_id: Conversation identifier
            q: Queue to remove
        """
        user_id = None

        with self.lock:
            if conversation_id in self.connections:
                # Find the user_id for this queue
                for conn in self.connections[conversation_id]:
                    if conn['queue'] == q:
                        user_id = conn['user_id']
                        break

                self.connections[conversation_id] = [
                    conn for conn in self.connections[conversation_id]
                    if conn['queue'] != q
                ]

                # Clean up empty conversation lists
                if not self.connections[conversation_id]:
                    del self.connections[conversation_id]

                # Update user presence
                if user_id is not None:
                    self.user_connections[user_id] = self.user_connections.get(user_id, 1) - 1

                    # If user has no more connections, mark as offline
                    if self.user_connections[user_id] <= 0:
                        self.online_users.discard(user_id)
                        if user_id in self.user_connections:
                            del self.user_connections[user_id]

        # Broadcast presence update if user went offline
        if user_id is not None and user_id not in self.online_users:
            self._broadcast_presence_update(user_id, 'offline')

    def broadcast(self, conversation_id: str, event_type: str, data: dict, exclude_user_id: Optional[int] = None):
        """
        Broadcast an event to all connections in a conversation.

        Args:
            conversation_id: Conversation to broadcast to
            event_type: Type of event (new_message, typing, user_joined, etc.)
            data: Event payload
            exclude_user_id: Optional user ID to exclude from broadcast (e.g., message sender)
        """
        with self.lock:
            if conversation_id not in self.connections:
                return

            event = {
                'event': event_type,
                'data': data,
                'timestamp': time.time()
            }

            dead_connections = []

            for conn in self.connections[conversation_id]:
                # Skip sender if exclude_user_id is specified
                if exclude_user_id and conn['user_id'] == exclude_user_id:
                    continue

                try:
                    # Non-blocking put - drop event if queue is full
                    conn['queue'].put_nowait(event)
                except queue.Full:
                    # Queue is full - mark for removal
                    dead_connections.append(conn)

            # Remove dead connections
            for dead_conn in dead_connections:
                self.connections[conversation_id].remove(dead_conn)

    def get_connection_count(self, conversation_id: str) -> int:
        """
        Get number of active connections for a conversation.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Number of active connections
        """
        with self.lock:
            return len(self.connections.get(conversation_id, []))

    def cleanup_stale_connections(self, max_age_seconds: int = 3600):
        """
        Remove connections that have been idle for too long.

        Args:
            max_age_seconds: Maximum connection age in seconds
        """
        current_time = time.time()

        with self.lock:
            for conversation_id in list(self.connections.keys()):
                self.connections[conversation_id] = [
                    conn for conn in self.connections[conversation_id]
                    if current_time - conn['connected_at'] < max_age_seconds
                ]

                if not self.connections[conversation_id]:
                    del self.connections[conversation_id]

    def _broadcast_presence_update(self, user_id: int, status: str):
        """
        Broadcast user presence update to all conversations.

        Args:
            user_id: User whose presence changed
            status: 'online' or 'offline'
        """
        # Broadcast to all conversations (no lock needed as broadcast has its own lock)
        for conversation_id in list(self.connections.keys()):
            self.broadcast(
                conversation_id=conversation_id,
                event_type='presence',
                data={
                    'user_id': user_id,
                    'status': status,
                    'timestamp': time.time()
                },
                exclude_user_id=None  # Everyone should see presence updates
            )

    def is_user_online(self, user_id: int) -> bool:
        """
        Check if a user is currently online.

        Args:
            user_id: User ID to check

        Returns:
            True if user is online, False otherwise
        """
        with self.lock:
            return user_id in self.online_users

    def get_online_users(self) -> List[int]:
        """
        Get list of all currently online user IDs.

        Returns:
            List of online user IDs
        """
        with self.lock:
            return list(self.online_users)


# Global SSE manager instance
sse_manager = SSEConnectionManager()
