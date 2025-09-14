import os
import json
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Iterator, IO, Any, Set
from collections import defaultdict
from filelock import FileLock
import uuid
import shutil

from ...models.tutorial_session import TutorialSession, WorkflowState
from ...models.session_data import SessionData, ProcessingStatus


class SessionManagerError(Exception):
    """Base exception for session manager operations"""
    pass


class SessionNotFoundError(SessionManagerError):
    """Session doesn't exist or has expired"""
    pass


class SessionStorageError(SessionManagerError):
    """File system operation failed"""
    pass


class ConcurrencyLimitError(SessionManagerError):
    """Too many concurrent sessions for IP"""
    pass


class StorageQuotaExceededError(SessionManagerError):
    """Storage quota exceeded for session or system"""
    pass


class FileLockTimeoutError(SessionManagerError):
    """Could not acquire file lock within timeout"""
    pass


class EnhancedSessionManager:
    """Enhanced session manager with streaming operations and storage management"""
    
    MAX_CONCURRENT_SESSIONS = 5
    MAX_SESSION_STORAGE = 100 * 1024 * 1024  # 100MB per session
    MAX_TOTAL_STORAGE = 1024 * 1024 * 1024   # 1GB total
    STREAMING_CHUNK_SIZE = 1024 * 1024       # 1MB chunks
    SESSION_TIMEOUT = 14400  # 4 hours in seconds
    
    def __init__(self, storage_root: Optional[str] = None):
        self.storage_root = Path(storage_root or os.getenv('CLINIPROMPT_STORAGE_ROOT', '/tmp/cliniprompt'))
        self.active_sessions: Dict[str, TutorialSession] = {}
        self.session_data: Dict[str, SessionData] = {}
        self.processing_files: Dict[str, Set[str]] = defaultdict(set)  # {session_id: {file_paths}}
        self.session_lock = threading.RLock()
        self.file_locks: Dict[str, FileLock] = {}
        
        # Create storage root directory
        self.storage_root.mkdir(parents=True, exist_ok=True)
    
    def create_session(self, user_preferences: Optional[Dict[str, Any]] = None, user_agent: str = "") -> str:
        """Create new tutorial session"""
        with self.session_lock:
            # Check concurrent session limit (simplified - would need IP tracking in real implementation)
            if len(self.active_sessions) >= self.MAX_CONCURRENT_SESSIONS:
                raise ConcurrencyLimitError(f"Maximum {self.MAX_CONCURRENT_SESSIONS} concurrent sessions")
            
            # Create session
            session = TutorialSession.create_new(
                user_agent=user_agent,
                preferences=user_preferences
            )
            
            # Create workspace
            workspace_path = self._create_session_workspace(session.session_id)
            session.workspace_path = workspace_path
            
            # Initialize session data
            session_data = SessionData()
            
            # Store session
            self.active_sessions[session.session_id] = session
            self.session_data[session.session_id] = session_data
            
            # Save session metadata
            self._save_session_metadata(session)
            
            return session.session_id
    
    def get_session(self, session_id: str) -> TutorialSession:
        """Get session by ID"""
        with self.session_lock:
            if session_id not in self.active_sessions:
                # Try to load from storage
                if not self._load_session_from_storage(session_id):
                    raise SessionNotFoundError(f"Session {session_id} not found")
            
            session = self.active_sessions[session_id]
            
            # Check if expired
            if session.is_expired():
                self.end_session(session_id)
                raise SessionNotFoundError(f"Session {session_id} has expired")
            
            return session
    
    def update_session_state(self, session_id: str, new_state: WorkflowState) -> bool:
        """Update session state"""
        try:
            session = self.get_session(session_id)
            session.update_state(new_state)
            
            # Save updated metadata
            self._save_session_metadata(session)
            
            return True
        except (SessionNotFoundError, ValueError):
            return False
    
    def end_session(self, session_id: str) -> bool:
        """End session and cleanup files"""
        with self.session_lock:
            try:
                # Check if safe to cleanup
                if not self.can_cleanup_session(session_id):
                    # Schedule cleanup after grace period
                    self.cleanup_with_grace_period(session_id)
                    return True
                
                # Remove from active sessions
                if session_id in self.active_sessions:
                    del self.active_sessions[session_id]
                
                if session_id in self.session_data:
                    del self.session_data[session_id]
                
                if session_id in self.processing_files:
                    del self.processing_files[session_id]
                
                # Cleanup files
                return self.cleanup_session_files(session_id)
                
            except Exception as e:
                raise SessionStorageError(f"Failed to end session: {str(e)}")
    
    def create_workspace(self, session_id: str) -> Path:
        """Create session workspace"""
        session = self.get_session(session_id)
        if session.workspace_path and session.workspace_path.exists():
            return session.workspace_path
        
        workspace_path = self._create_session_workspace(session_id)
        session.workspace_path = workspace_path
        return workspace_path
    
    def save_large_file(
        self, 
        session_id: str, 
        file_stream: IO[bytes], 
        file_type: str, 
        filename: str
    ) -> Path:
        """Save large file using streaming to prevent memory issues"""
        session_path = self._get_session_path(session_id)
        file_path = session_path / "files" / file_type / filename
        
        # Check storage quota before starting
        file_size = self._estimate_stream_size(file_stream)
        if not self.check_storage_quota(session_id, file_size):
            raise StorageQuotaExceededError(f"File would exceed storage quota: {file_size} bytes")
        
        # Use file locking to prevent concurrent access
        lock_path = session_path / "metadata" / "locks" / f"{filename}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with FileLock(str(lock_path), timeout=30):
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(file_path, 'wb') as f:
                    total_written = 0
                    while True:
                        chunk = file_stream.read(self.STREAMING_CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        total_written += len(chunk)
                        
                        # Check quota during write
                        if total_written > self.MAX_SESSION_STORAGE:
                            file_path.unlink()  # Delete partial file
                            raise StorageQuotaExceededError("File size exceeded during upload")
                            
        except Exception as e:
            if file_path.exists():
                file_path.unlink()
            raise SessionStorageError(f"Failed to save file: {str(e)}")
                        
        return file_path
    
    def get_file_stream(self, session_id: str, file_path: str) -> Iterator[bytes]:
        """Get file as stream for processing"""
        full_path = self._resolve_file_path(session_id, file_path)
        lock_path = self._get_lock_path(session_id, file_path)
        
        try:
            with FileLock(str(lock_path), timeout=30):
                with open(full_path, 'rb') as f:
                    while True:
                        chunk = f.read(self.STREAMING_CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
        except Exception as e:
            raise SessionStorageError(f"Failed to read file stream: {str(e)}")
                    
    def mark_file_processing(self, session_id: str, file_path: str, service_name: str) -> bool:
        """Mark file as being processed by service"""
        with self.session_lock:
            self.processing_files[session_id].add(f"{file_path}:{service_name}")
            return True
            
    def unmark_file_processing(self, session_id: str, file_path: str, service_name: str) -> bool:
        """Unmark file when processing complete"""
        with self.session_lock:
            self.processing_files[session_id].discard(f"{file_path}:{service_name}")
            return True
            
    def can_cleanup_session(self, session_id: str) -> bool:
        """Check if session can be safely cleaned up"""
        return len(self.processing_files[session_id]) == 0
    
    def check_storage_quota(self, session_id: str, file_size: int) -> bool:
        """Check if adding file would exceed quotas"""
        current_session_size = self._get_session_storage_size(session_id)
        current_total_size = self._get_total_storage_size()
        
        if current_session_size + file_size > self.MAX_SESSION_STORAGE:
            return False
            
        if current_total_size + file_size > self.MAX_TOTAL_STORAGE:
            # Try to cleanup old sessions to make room
            self._cleanup_oldest_sessions(file_size)
            return self._get_total_storage_size() + file_size <= self.MAX_TOTAL_STORAGE
            
        return True
    
    def cleanup_session_files(self, session_id: str, force: bool = False) -> bool:
        """Remove all files for a session"""
        if not force and not self.can_cleanup_session(session_id):
            return False
        
        try:
            session_path = self._get_session_path(session_id)
            if session_path.exists():
                shutil.rmtree(session_path)
            return True
        except Exception as e:
            raise SessionStorageError(f"Failed to cleanup session files: {str(e)}")
    
    def cleanup_with_grace_period(self, session_id: str, grace_minutes: int = 5) -> None:
        """Attempt cleanup with grace period for active processing"""
        def delayed_cleanup():
            import time
            time.sleep(grace_minutes * 60)
            if self.can_cleanup_session(session_id):
                self.cleanup_session_files(session_id, force=True)
        
        if not self.can_cleanup_session(session_id):
            threading.Thread(target=delayed_cleanup, daemon=True).start()
        else:
            self.cleanup_session_files(session_id)
    
    def get_session_data(self, session_id: str) -> SessionData:
        """Get session data"""
        if session_id not in self.session_data:
            self.session_data[session_id] = SessionData()
        return self.session_data[session_id]
    
    # Private helper methods
    def _create_session_workspace(self, session_id: str) -> Path:
        """Create session workspace with proper permissions and structure"""
        session_path = self._get_session_path(session_id)
        
        # Create directory structure
        subdirs = ['metadata', 'files/audio/original', 'files/audio/processed', 
                  'files/pdfs', 'files/generated/scripts', 'files/generated/audio', 
                  'temp', 'logs', 'metadata/locks']
        
        for subdir in subdirs:
            (session_path / subdir).mkdir(parents=True, exist_ok=True, mode=0o700)
            
        return session_path
    
    def _get_session_path(self, session_id: str) -> Path:
        """Get path to session directory"""
        return self.storage_root / "sessions" / session_id
    
    def _save_session_metadata(self, session: TutorialSession) -> None:
        """Save session metadata to disk"""
        session_path = self._get_session_path(session.session_id)
        metadata_path = session_path / "metadata" / "session.json"
        
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, 'w') as f:
            json.dump(session.to_dict(), f, indent=2)
    
    def _load_session_from_storage(self, session_id: str) -> bool:
        """Try to load session from storage"""
        try:
            session_path = self._get_session_path(session_id)
            metadata_path = session_path / "metadata" / "session.json"
            
            if not metadata_path.exists():
                return False
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Reconstruct session (simplified - would need full deserialization)
            return False  # For now, don't support persistence
            
        except Exception:
            return False
    
    def _get_session_storage_size(self, session_id: str) -> int:
        """Get total storage size for session"""
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return 0
        
        total_size = 0
        for file_path in session_path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size
    
    def _get_total_storage_size(self) -> int:
        """Get total storage size across all sessions"""
        if not self.storage_root.exists():
            return 0
        
        total_size = 0
        for file_path in self.storage_root.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size
    
    def _estimate_stream_size(self, file_stream: IO[bytes]) -> int:
        """Estimate size of stream (simplified)"""
        # In real implementation, would peek at content-length header or buffer
        return 0  # Return 0 for now - would need proper implementation
    
    def _resolve_file_path(self, session_id: str, file_path: str) -> Path:
        """Resolve relative file path to absolute path"""
        session_path = self._get_session_path(session_id)
        return session_path / "files" / file_path
    
    def _get_lock_path(self, session_id: str, file_path: str) -> Path:
        """Get lock file path for given file"""
        session_path = self._get_session_path(session_id)
        filename = Path(file_path).name
        return session_path / "metadata" / "locks" / f"{filename}.lock"
    
    def _cleanup_oldest_sessions(self, space_needed: int) -> int:
        """Cleanup oldest completed sessions to free space"""
        # Simplified implementation - would need proper age tracking
        return 0


# Create global session manager instance
session_manager = EnhancedSessionManager()