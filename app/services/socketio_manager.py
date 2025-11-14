"""
Flask-SocketIO Manager for real-time chat communication
Replaces SSE with WebSocket-based communication
"""
from flask_socketio import SocketIO, emit, join_room, leave_room
from typing import Dict, Set
from threading import Lock


class SocketIOConnectionManager:
    """
    Manages Socket.IO connections and user presence for real-time chat.

    Tracks user presence and provides methods for broadcasting events
    to conversation rooms.
    """

    def __init__(self):
        self.online_users: Set[int] = set()  # Track currently online user IDs
        self.user_sessions: Dict[int, Set[str]] = {}  # Map user_id to set of session IDs
        self.lock = Lock()

    def user_connected(self, user_id: int, session_id: str):
        """
        Mark a user as connected.

        Args:
            user_id: User ID
            session_id: Socket.IO session ID
        """
        with self.lock:
            was_offline = user_id not in self.online_users

            self.online_users.add(user_id)

            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = set()
            self.user_sessions[user_id].add(session_id)

        return was_offline

    def user_disconnected(self, user_id: int, session_id: str):
        """
        Handle user disconnection.

        Args:
            user_id: User ID
            session_id: Socket.IO session ID

        Returns:
            True if user went offline (no more sessions), False otherwise
        """
        with self.lock:
            if user_id in self.user_sessions:
                self.user_sessions[user_id].discard(session_id)

                # If user has no more sessions, mark as offline
                if not self.user_sessions[user_id]:
                    self.online_users.discard(user_id)
                    del self.user_sessions[user_id]
                    return True

        return False

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

    def get_online_users(self) -> list:
        """
        Get list of all currently online user IDs.

        Returns:
            List of online user IDs
        """
        with self.lock:
            return list(self.online_users)


# Global SocketIO connection manager instance
socketio_manager = SocketIOConnectionManager()


def init_socketio_events(socketio: SocketIO):
    """
    Initialize Socket.IO event handlers.

    Args:
        socketio: Flask-SocketIO instance
    """
    from flask import request
    from flask_login import current_user

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        if not current_user.is_authenticated:
            return False  # Reject unauthenticated connections

        was_offline = socketio_manager.user_connected(current_user.id, request.sid)

        # Join user's personal room for notifications
        user_room = f"user_{current_user.id}"
        join_room(user_room)

        # Broadcast presence update if user just came online
        if was_offline:
            emit('presence', {
                'user_id': current_user.id,
                'status': 'online'
            }, broadcast=True, include_self=False)

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        if current_user.is_authenticated:
            went_offline = socketio_manager.user_disconnected(current_user.id, request.sid)

            # Broadcast presence update if user went offline
            if went_offline:
                emit('presence', {
                    'user_id': current_user.id,
                    'status': 'offline'
                }, broadcast=True, include_self=False)

    @socketio.on('join_conversation')
    def handle_join_conversation(data):
        """
        Handle client joining a conversation room.

        Args:
            data: Dict with 'conversation_id' key
        """
        if not current_user.is_authenticated:
            return

        conversation_id = data.get('conversation_id')
        if conversation_id:
            join_room(conversation_id)
            emit('joined', {'conversation_id': conversation_id})

    @socketio.on('leave_conversation')
    def handle_leave_conversation(data):
        """
        Handle client leaving a conversation room.

        Args:
            data: Dict with 'conversation_id' key
        """
        if not current_user.is_authenticated:
            return

        conversation_id = data.get('conversation_id')
        if conversation_id:
            leave_room(conversation_id)
            emit('left', {'conversation_id': conversation_id})

    @socketio.on('typing')
    def handle_typing(data):
        """
        Handle typing indicator from client.

        Args:
            data: Dict with 'conversation_id' and 'is_typing' keys
        """
        if not current_user.is_authenticated:
            return

        conversation_id = data.get('conversation_id')
        is_typing = data.get('is_typing', False)

        if conversation_id:
            # Broadcast typing status to room, excluding sender
            emit('typing', {
                'user_id': current_user.id,
                'user_name': current_user.full_name,
                'is_typing': is_typing
            }, room=conversation_id, include_self=False)
