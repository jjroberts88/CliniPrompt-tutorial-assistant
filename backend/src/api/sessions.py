from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from ..services.session_manager import session_manager, SessionNotFoundError, ConcurrencyLimitError
from ..models.tutorial_session import WorkflowState
from ..models.audio_recording import AudioRecording


logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class UserPreferences(BaseModel):
    """User preferences model"""
    preferred_voice: Optional[str] = "professional_female"
    summary_style: Optional[str] = "conversational"
    emphasis_areas: List[str] = []
    
    @validator('preferred_voice')
    def validate_voice(cls, v):
        allowed_voices = ["professional_female", "professional_male", "conversational_female", "conversational_male"]
        if v not in allowed_voices:
            raise ValueError(f"Invalid voice. Must be one of: {allowed_voices}")
        return v
    
    @validator('summary_style')
    def validate_style(cls, v):
        allowed_styles = ["conversational", "technical", "basic"]
        if v not in allowed_styles:
            raise ValueError(f"Invalid style. Must be one of: {allowed_styles}")
        return v


class CreateSessionRequest(BaseModel):
    """Request model for creating a session"""
    user_agent: Optional[str] = ""
    preferences: Optional[UserPreferences] = None


class SessionResponse(BaseModel):
    """Response model for session creation"""
    session_id: str
    state: str
    created_at: str
    expires_at: str


class AudioFileInfo(BaseModel):
    """Audio file information"""
    file_name: str
    file_size_mb: float
    duration_seconds: Optional[int] = None
    mime_type: str
    quality_metrics: Optional[Dict[str, Any]] = None


class AudioUploadResponse(BaseModel):
    """Response for audio upload"""
    file_info: AudioFileInfo
    session_state: str


class SessionDetail(BaseModel):
    """Detailed session information"""
    session_id: str
    state: str
    created_at: str
    expires_at: str
    audio_file: Optional[AudioFileInfo] = None
    supplementary_content: List[Dict[str, Any]] = []
    processing_status: Optional[Dict[str, Any]] = None
    generated_summary: Optional[Dict[str, Any]] = None


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(request: CreateSessionRequest = CreateSessionRequest()):
    """Create a new tutorial session"""
    try:
        # Convert preferences to dict
        preferences_dict = None
        if request.preferences:
            preferences_dict = request.preferences.dict()
        
        # Create session
        session_id = session_manager.create_session(
            user_preferences=preferences_dict,
            user_agent=request.user_agent
        )
        
        # Get created session
        session = session_manager.get_session(session_id)
        
        logger.info(f"Created session {session_id}")
        
        return SessionResponse(
            session_id=session.session_id,
            state=session.state.value,
            created_at=session.created_at.isoformat(),
            expires_at=session.expires_at.isoformat()
        )
        
    except ConcurrencyLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create session")


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str):
    """Get session details"""
    try:
        session = session_manager.get_session(session_id)
        session_data = session_manager.get_session_data(session_id)
        
        # Build detailed response
        detail = SessionDetail(
            session_id=session.session_id,
            state=session.state.value,
            created_at=session.created_at.isoformat(),
            expires_at=session.expires_at.isoformat(),
            audio_file=None,  # Would populate from actual audio data
            supplementary_content=[],  # Would populate from actual content
            processing_status=session_data.processing_status.to_dict() if session_data.processing_status else None,
            generated_summary=None  # Would populate from actual summary
        )
        
        return detail
        
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve session")


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str):
    """Delete session and cleanup files"""
    try:
        success = session_manager.end_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
            
        logger.info(f"Deleted session {session_id}")
        
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete session")


@router.post("/sessions/{session_id}/audio", response_model=AudioUploadResponse, status_code=201)
async def upload_audio(session_id: str, audio_file: UploadFile = File(...)):
    """Upload audio file for tutorial processing"""
    try:
        # Validate session exists
        session = session_manager.get_session(session_id)
        
        # Validate file
        if not audio_file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
            
        # Check file size (30MB limit)
        MAX_SIZE = 30 * 1024 * 1024  # 30MB
        content = await audio_file.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="File size exceeds 30MB limit")
        
        # Validate MIME type and file extension
        allowed_types = ["audio/mp3", "audio/mpeg", "audio/wav", "audio/m4a", "audio/mp4", "audio/ogg", "application/octet-stream"]
        allowed_extensions = [".mp3", ".wav", ".m4a", ".mp4", ".ogg"]
        
        logger.info(f"Received file with content type: {audio_file.content_type}, filename: {audio_file.filename}")
        
        # Check if content type is valid or if it's octet-stream with valid extension
        file_extension = audio_file.filename.lower().split('.')[-1] if audio_file.filename else ""
        is_valid_extension = any(audio_file.filename.lower().endswith(ext) for ext in allowed_extensions)
        
        if audio_file.content_type not in allowed_types and not is_valid_extension:
            raise HTTPException(status_code=400, detail=f"Invalid file format. Received: {audio_file.content_type}, Supported extensions: {allowed_extensions}")
        
        if audio_file.content_type == "application/octet-stream" and not is_valid_extension:
            raise HTTPException(status_code=400, detail=f"Invalid file format. File extension must be one of: {allowed_extensions}")
        
        # Create workspace and save file
        workspace = session_manager.create_workspace(session_id)
        audio_path = workspace / "files" / "audio" / "original" / audio_file.filename
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        with open(audio_path, "wb") as f:
            f.write(content)
        
        # Create AudioRecording model
        audio_recording = AudioRecording.create_from_upload(
            file_name=audio_file.filename,
            file_content=content,
            mime_type=audio_file.content_type,
            temporary_path=audio_path
        )
        
        # Update session state
        session_manager.update_session_state(session_id, WorkflowState.AUDIO_UPLOADED)
        
        logger.info(f"Uploaded audio file {audio_file.filename} to session {session_id}")
        
        # Build response
        file_info = AudioFileInfo(
            file_name=audio_recording.file_name,
            file_size_mb=audio_recording.file_size_mb,
            duration_seconds=audio_recording.duration_seconds,
            mime_type=audio_recording.mime_type,
            quality_metrics=audio_recording.quality_metrics.to_dict() if audio_recording.quality_metrics else None
        )
        
        return AudioUploadResponse(
            file_info=file_info,
            session_state="AUDIO_UPLOADED"
        )
        
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to upload audio to session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload audio file: {str(e)}")


class ProcessingRequest(BaseModel):
    """Request model for starting processing"""
    summary_duration: int = 20
    focus_areas: List[str] = []
    voice_style: Optional[str] = "professional_female"
    summary_style: Optional[str] = "conversational"
    custom_prompts: Optional[Dict[str, str]] = None
    
    @validator('summary_duration')
    def validate_duration(cls, v):
        if v < 10 or v > 30:
            raise ValueError("Summary duration must be between 10 and 30 minutes")
        return v


class ProcessingStartedResponse(BaseModel):
    """Response for processing initiation"""
    task_id: str
    session_state: str
    estimated_completion: Optional[str] = None


@router.post("/sessions/{session_id}/process", response_model=ProcessingStartedResponse, status_code=202)
async def start_processing(session_id: str, request: ProcessingRequest):
    """Start processing the tutorial content"""
    try:
        # Validate session exists and is in correct state
        session = session_manager.get_session(session_id)
        
        if session.state not in [WorkflowState.AUDIO_UPLOADED, WorkflowState.CONTENT_ADDED]:
            raise HTTPException(
                status_code=409, 
                detail=f"Session not ready for processing. Current state: {session.state.value}"
            )
        
        # Get session data and start processing
        session_data = session_manager.get_session_data(session_id)
        processing_status = session_data.start_processing("Initializing processing...")
        
        # Update session state to PROCESSING
        session_manager.update_session_state(session_id, WorkflowState.PROCESSING)
        
        # TODO: Implement actual background processing task
        # For now, simulate processing initiation
        
        logger.info(f"Started processing for session {session_id} with duration {request.summary_duration}min")
        
        return ProcessingStartedResponse(
            task_id=processing_status.task_id,
            session_state="PROCESSING"
        )
        
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start processing for session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")


@router.get("/sessions/{session_id}/status")
async def get_processing_status(session_id: str):
    """Get processing status"""
    try:
        session = session_manager.get_session(session_id)
        session_data = session_manager.get_session_data(session_id)
        
        if not session_data.processing_status:
            raise HTTPException(status_code=404, detail="No processing status available")
        
        return session_data.processing_status.to_dict()
        
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get status for session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get processing status: {str(e)}")