"""
Session management for the LumaHealth Conversational AI Service.

This module handles in-memory session state management for conversational flows.
In production, this would be backed by Redis or another persistent store.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional
from threading import Lock

from .models import SessionState


class SessionManager:
    """
    In-memory session manager for conversational AI flows.
    
    Manages session state including verification status, patient ID,
    and conversation context. Thread-safe for concurrent access.
    """
    
    def __init__(self, session_timeout_minutes: int = 30):
        self._sessions: Dict[str, SessionState] = {}
        self._lock = Lock()
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session state by ID."""
        with self._lock:
            session = self._sessions.get(session_id)
            
            # Check if session has expired
            if session and self._is_expired(session):
                del self._sessions[session_id]
                return None
            
            return session
    
    def get_or_create_session(self, session_id: str) -> SessionState:
        """Get existing session or create new one."""
        session = self.get_session(session_id)
        
        if session is None:
            with self._lock:
                session = SessionState(session_id=session_id)
                self._sessions[session_id] = session
        
        return session
    
    def update_session(self, session_id: str, session_state: SessionState) -> None:
        """Update session state."""
        with self._lock:
            session_state.last_activity = datetime.utcnow()
            self._sessions[session_id] = session_state
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None
    
    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions and return count of removed sessions."""
        expired_sessions = []
        
        with self._lock:
            for session_id, session in self._sessions.items():
                if self._is_expired(session):
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self._sessions[session_id]
        
        return len(expired_sessions)
    
    def get_session_count(self) -> int:
        """Get total number of active sessions."""
        with self._lock:
            return len(self._sessions)
    
    def get_verified_session_count(self) -> int:
        """Get number of verified sessions."""
        with self._lock:
            return sum(1 for session in self._sessions.values() if session.is_verified)
    
    def _is_expired(self, session: SessionState) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() - session.last_activity > self.session_timeout
    
    def get_session_stats(self) -> dict:
        """Get session statistics for monitoring."""
        with self._lock:
            total = len(self._sessions)
            verified = sum(1 for session in self._sessions.values() if session.is_verified)
            expired = sum(1 for session in self._sessions.values() if self._is_expired(session))
            
            return {
                "total_sessions": total,
                "verified_sessions": verified,
                "expired_sessions": expired,
                "active_sessions": total - expired
            }
