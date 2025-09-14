from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from pathlib import Path
import uuid


class WorkflowState(Enum):
    """Session workflow states"""
    INITIAL = "INITIAL"
    AUDIO_UPLOADED = "AUDIO_UPLOADED" 
    CONTENT_ADDED = "CONTENT_ADDED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


@dataclass
class UserPreferences:
    """User preferences for tutorial processing"""
    preferred_voice: str = "professional_female"
    summary_style: str = "conversational"
    emphasis_areas: List[str] = field(default_factory=list)
    custom_terminology: Dict[str, str] = field(default_factory=dict)


@dataclass
class TutorialSession:
    """Represents the main workflow session for creating a medical tutorial summary"""
    
    session_id: str
    state: WorkflowState
    created_at: datetime
    last_updated: datetime
    expires_at: datetime
    user_agent: str
    user_preferences: UserPreferences = field(default_factory=UserPreferences)
    workspace_path: Optional[Path] = None
    
    @classmethod
    def create_new(
        cls,
        user_agent: str = "",
        preferences: Optional[Dict[str, Any]] = None,
        session_timeout_hours: int = 4
    ) -> "TutorialSession":
        """Create a new tutorial session"""
        now = datetime.now()
        session_id = str(uuid.uuid4())
        
        # Parse preferences
        user_prefs = UserPreferences()
        if preferences:
            user_prefs.preferred_voice = preferences.get("preferred_voice", user_prefs.preferred_voice)
            user_prefs.summary_style = preferences.get("summary_style", user_prefs.summary_style) 
            user_prefs.emphasis_areas = preferences.get("emphasis_areas", [])
            user_prefs.custom_terminology = preferences.get("custom_terminology", {})
        
        return cls(
            session_id=session_id,
            state=WorkflowState.INITIAL,
            created_at=now,
            last_updated=now,
            expires_at=now + timedelta(hours=session_timeout_hours),
            user_agent=user_agent,
            user_preferences=user_prefs
        )
    
    def update_state(self, new_state: WorkflowState) -> None:
        """Update session state and last_updated timestamp"""
        if not self._is_valid_state_transition(self.state, new_state):
            raise ValueError(f"Invalid state transition from {self.state} to {new_state}")
        
        self.state = new_state
        self.last_updated = datetime.now()
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        return datetime.now() > self.expires_at
    
    def extend_expiration(self, additional_hours: int = 4) -> None:
        """Extend session expiration time"""
        self.expires_at = datetime.now() + timedelta(hours=additional_hours)
        self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for API responses"""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "user_agent": self.user_agent,
            "preferences": {
                "preferred_voice": self.user_preferences.preferred_voice,
                "summary_style": self.user_preferences.summary_style,
                "emphasis_areas": self.user_preferences.emphasis_areas,
                "custom_terminology": self.user_preferences.custom_terminology
            }
        }
    
    @staticmethod
    def _is_valid_state_transition(current: WorkflowState, new: WorkflowState) -> bool:
        """Validate state transitions"""
        valid_transitions = {
            WorkflowState.INITIAL: [WorkflowState.AUDIO_UPLOADED, WorkflowState.ERROR],
            WorkflowState.AUDIO_UPLOADED: [WorkflowState.CONTENT_ADDED, WorkflowState.PROCESSING, WorkflowState.ERROR],
            WorkflowState.CONTENT_ADDED: [WorkflowState.PROCESSING, WorkflowState.ERROR],
            WorkflowState.PROCESSING: [WorkflowState.COMPLETED, WorkflowState.ERROR],
            WorkflowState.COMPLETED: [WorkflowState.INITIAL, WorkflowState.ERROR],  # Allow reset
            WorkflowState.ERROR: [WorkflowState.PROCESSING, WorkflowState.INITIAL]  # Allow retry
        }
        
        return new in valid_transitions.get(current, [])