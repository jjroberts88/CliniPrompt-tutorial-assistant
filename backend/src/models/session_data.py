from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid


class ProcessingStatusType(Enum):
    """Processing status types"""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ProcessingStatus:
    """Processing status information"""
    task_id: str
    status: ProcessingStatusType
    progress: int  # 0-100
    current_step: str
    start_time: datetime
    estimated_completion: Optional[datetime] = None
    processing_time_seconds: Optional[int] = None
    error_message: Optional[str] = None
    
    @classmethod
    def create_new(cls, current_step: str = "Initializing...") -> "ProcessingStatus":
        """Create new processing status"""
        return cls(
            task_id=str(uuid.uuid4()),
            status=ProcessingStatusType.PENDING,
            progress=0,
            current_step=current_step,
            start_time=datetime.now()
        )
    
    def update_progress(self, progress: int, current_step: str) -> None:
        """Update processing progress"""
        self.progress = max(0, min(100, progress))  # Clamp to 0-100
        self.current_step = current_step
        
        if progress >= 100:
            self.status = ProcessingStatusType.COMPLETED
            self.processing_time_seconds = int((datetime.now() - self.start_time).total_seconds())
    
    def mark_error(self, error_message: str) -> None:
        """Mark processing as failed"""
        self.status = ProcessingStatusType.ERROR
        self.error_message = error_message
        self.processing_time_seconds = int((datetime.now() - self.start_time).total_seconds())
    
    def mark_processing(self) -> None:
        """Mark as actively processing"""
        self.status = ProcessingStatusType.PROCESSING
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "current_step": self.current_step,
            "start_time": self.start_time.isoformat(),
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "processing_time_seconds": self.processing_time_seconds,
            "error": self.error_message
        }


@dataclass
class ResourceUsage:
    """Resource usage tracking"""
    memory_usage_mb: float = 0.0
    storage_usage_mb: float = 0.0
    processing_time_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "memory_usage_mb": self.memory_usage_mb,
            "storage_usage_mb": self.storage_usage_mb,
            "processing_time_seconds": self.processing_time_seconds
        }


@dataclass
class SessionData:
    """Temporary runtime data for session management and progress tracking"""
    
    current_step: str = "Session initialized"
    progress_percentage: int = 0
    error_log: List[str] = field(default_factory=list)
    processing_status: Optional[ProcessingStatus] = None
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    
    def add_error(self, error_message: str) -> None:
        """Add error to error log with timestamp"""
        timestamp = datetime.now().isoformat()
        formatted_error = f"[{timestamp}] {error_message}"
        self.error_log.append(formatted_error)
        
        # Keep only last 50 errors
        if len(self.error_log) > 50:
            self.error_log = self.error_log[-50:]
    
    def update_progress(self, progress: int, step: str) -> None:
        """Update overall progress"""
        self.progress_percentage = max(0, min(100, progress))
        self.current_step = step
        
        if self.processing_status:
            self.processing_status.update_progress(progress, step)
    
    def start_processing(self, initial_step: str = "Starting processing...") -> ProcessingStatus:
        """Start new processing task"""
        self.processing_status = ProcessingStatus.create_new(initial_step)
        self.processing_status.mark_processing()
        self.current_step = initial_step
        self.progress_percentage = 0
        return self.processing_status
    
    def complete_processing(self) -> None:
        """Mark processing as completed"""
        if self.processing_status:
            self.processing_status.update_progress(100, "Processing completed")
        self.progress_percentage = 100
        self.current_step = "Completed"
    
    def fail_processing(self, error_message: str) -> None:
        """Mark processing as failed"""
        if self.processing_status:
            self.processing_status.mark_error(error_message)
        self.add_error(error_message)
        self.current_step = f"Error: {error_message}"
    
    def update_resource_usage(
        self, 
        memory_mb: Optional[float] = None,
        storage_mb: Optional[float] = None,
        processing_time: Optional[float] = None
    ) -> None:
        """Update resource usage metrics"""
        if memory_mb is not None:
            self.resource_usage.memory_usage_mb = memory_mb
        if storage_mb is not None:
            self.resource_usage.storage_usage_mb = storage_mb
        if processing_time is not None:
            self.resource_usage.processing_time_seconds = processing_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "current_step": self.current_step,
            "progress_percentage": self.progress_percentage,
            "error_log": self.error_log[-10:],  # Return only last 10 errors for API
            "processing_status": self.processing_status.to_dict() if self.processing_status else None,
            "resource_usage": self.resource_usage.to_dict()
        }