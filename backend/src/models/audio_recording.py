from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pathlib import Path


class AudioProcessingStatus(Enum):
    """Audio processing status states"""
    UPLOADED = "UPLOADED"
    TRANSCRIBING = "TRANSCRIBING" 
    TRANSCRIBED = "TRANSCRIBED"
    ANALYZING = "ANALYZING"
    PROCESSED = "PROCESSED"
    ERROR = "ERROR"


@dataclass
class QualityMetrics:
    """Audio quality indicators"""
    signal_to_noise_ratio: float = 0.0
    estimated_speech_percentage: float = 0.0
    clarity_score: float = 0.0  # 0.0-1.0
    speaker_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "signal_to_noise_ratio": self.signal_to_noise_ratio,
            "estimated_speech_percentage": self.estimated_speech_percentage,
            "clarity_score": self.clarity_score,
            "speaker_count": self.speaker_count
        }


@dataclass
class AudioRecording:
    """Contains the primary tutorial audio file and associated metadata"""
    
    file_name: str
    file_size_bytes: int
    mime_type: str
    upload_timestamp: datetime
    processing_status: AudioProcessingStatus
    temporary_path: Path
    duration_seconds: Optional[int] = None
    quality_metrics: QualityMetrics = field(default_factory=QualityMetrics)
    transcription_text: Optional[str] = None
    error_message: Optional[str] = None
    
    @property
    def file_size_mb(self) -> float:
        """File size in megabytes"""
        return self.file_size_bytes / (1024 * 1024)
    
    @classmethod
    def create_from_upload(
        cls,
        file_name: str,
        file_content: bytes,
        mime_type: str,
        temporary_path: Path
    ) -> "AudioRecording":
        """Create AudioRecording from uploaded file"""
        # Validate file size (30MB limit)
        max_size = 30 * 1024 * 1024  # 30MB in bytes
        if len(file_content) > max_size:
            raise ValueError(f"File size {len(file_content)} exceeds maximum of {max_size} bytes")
        
        # Validate MIME type (allow application/octet-stream for generic binary files)
        allowed_types = ["audio/mp3", "audio/mpeg", "audio/wav", "audio/m4a", "audio/mp4", "audio/ogg", "application/octet-stream"]
        if mime_type not in allowed_types:
            raise ValueError(f"Unsupported MIME type: {mime_type}")
        
        # Save file to temporary path
        temporary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temporary_path, "wb") as f:
            f.write(file_content)
        
        return cls(
            file_name=file_name,
            file_size_bytes=len(file_content),
            mime_type=mime_type,
            upload_timestamp=datetime.now(),
            processing_status=AudioProcessingStatus.UPLOADED,
            temporary_path=temporary_path
        )
    
    def update_status(self, new_status: AudioProcessingStatus, error_message: Optional[str] = None) -> None:
        """Update processing status"""
        self.processing_status = new_status
        if error_message:
            self.error_message = error_message
    
    def set_transcription(self, transcription_text: str) -> None:
        """Set transcription text and update status"""
        self.transcription_text = transcription_text
        self.processing_status = AudioProcessingStatus.TRANSCRIBED
    
    def set_quality_metrics(self, metrics: QualityMetrics) -> None:
        """Set audio quality metrics"""
        self.quality_metrics = metrics
    
    def set_duration(self, duration_seconds: int) -> None:
        """Set audio duration"""
        self.duration_seconds = duration_seconds
    
    def is_valid_for_processing(self) -> bool:
        """Check if audio is valid for processing"""
        return (
            self.processing_status in [AudioProcessingStatus.UPLOADED, AudioProcessingStatus.PROCESSED] and
            self.file_size_bytes > 0 and
            self.temporary_path.exists()
        )
    
    def cleanup_files(self) -> None:
        """Clean up temporary audio files"""
        if self.temporary_path.exists():
            self.temporary_path.unlink()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "file_name": self.file_name,
            "file_size_bytes": self.file_size_bytes,
            "file_size_mb": self.file_size_mb,
            "mime_type": self.mime_type,
            "upload_timestamp": self.upload_timestamp.isoformat(),
            "processing_status": self.processing_status.value,
            "duration_seconds": self.duration_seconds,
            "quality_metrics": self.quality_metrics.to_dict() if self.quality_metrics else None,
            "has_transcription": self.transcription_text is not None,
            "error_message": self.error_message
        }