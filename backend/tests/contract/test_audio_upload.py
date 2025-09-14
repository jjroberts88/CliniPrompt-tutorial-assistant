import pytest
import httpx
import io
from pathlib import Path


class TestAudioUploadContract:
    """Contract tests for POST /api/v1/sessions/{session_id}/audio endpoint"""

    @pytest.fixture
    def sample_audio_data(self):
        """Create sample audio file data for testing"""
        # Create minimal MP3-like data for testing
        # In real tests, would use actual audio file
        return b"ID3\x03\x00\x00\x00" + b"\x00" * 1000  # Minimal MP3 header + data

    @pytest.fixture
    def large_audio_data(self):
        """Create large audio file data for size limit testing"""
        return b"ID3\x03\x00\x00\x00" + b"\x00" * (32 * 1024 * 1024)  # 32MB

    @pytest.mark.asyncio
    async def test_upload_audio_success(self, sample_audio_data):
        """Test successful audio file upload"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            # Create session first
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            # Upload audio file
            files = {"audio_file": ("test.mp3", sample_audio_data, "audio/mpeg")}
            response = await client.post(
                f"/api/v1/sessions/{session_id}/audio",
                files=files
            )
            
        assert response.status_code == 201
        data = response.json()
        
        # Validate response structure
        assert "file_info" in data
        assert "session_state" in data
        
        # Validate file info structure
        file_info = data["file_info"]
        assert "file_name" in file_info
        assert "file_size_mb" in file_info
        assert "mime_type" in file_info
        assert "quality_metrics" in file_info
        
        # Validate values
        assert data["session_state"] == "AUDIO_UPLOADED"
        assert file_info["file_name"] == "test.mp3"
        assert file_info["mime_type"] == "audio/mpeg"

    @pytest.mark.asyncio
    async def test_upload_audio_invalid_session(self, sample_audio_data):
        """Test audio upload to non-existent session"""
        fake_session_id = "00000000-0000-0000-0000-000000000000"
        
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            files = {"audio_file": ("test.mp3", sample_audio_data, "audio/mpeg")}
            response = await client.post(
                f"/api/v1/sessions/{fake_session_id}/audio",
                files=files
            )
            
        assert response.status_code == 404
        error_data = response.json()
        assert "not found" in error_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_upload_audio_file_too_large(self, large_audio_data):
        """Test audio upload exceeding 30MB limit"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            files = {"audio_file": ("large.mp3", large_audio_data, "audio/mpeg")}
            response = await client.post(
                f"/api/v1/sessions/{session_id}/audio",
                files=files
            )
            
        assert response.status_code == 413
        error_data = response.json()
        assert "30MB" in error_data["error"]["message"]

    @pytest.mark.asyncio
    async def test_upload_audio_invalid_format(self):
        """Test audio upload with unsupported file format"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            # Upload text file as audio
            invalid_data = b"This is not audio data"
            files = {"audio_file": ("test.txt", invalid_data, "text/plain")}
            response = await client.post(
                f"/api/v1/sessions/{session_id}/audio",
                files=files
            )
            
        assert response.status_code == 400
        error_data = response.json()
        assert "format" in error_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_upload_audio_missing_file(self):
        """Test audio upload without file"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            response = await client.post(
                f"/api/v1/sessions/{session_id}/audio",
                files={}
            )
            
        assert response.status_code == 422  # Missing required field

    @pytest.mark.asyncio
    async def test_upload_audio_duplicate(self, sample_audio_data):
        """Test uploading audio to session that already has audio"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            # First upload
            files = {"audio_file": ("test1.mp3", sample_audio_data, "audio/mpeg")}
            first_response = await client.post(
                f"/api/v1/sessions/{session_id}/audio",
                files=files
            )
            
            # Second upload (should replace or error)
            files = {"audio_file": ("test2.mp3", sample_audio_data, "audio/mpeg")}
            second_response = await client.post(
                f"/api/v1/sessions/{session_id}/audio",
                files=files
            )
            
        # Implementation decision: replace existing or error
        # For this spec, assume replacement is allowed
        assert second_response.status_code in [201, 409]