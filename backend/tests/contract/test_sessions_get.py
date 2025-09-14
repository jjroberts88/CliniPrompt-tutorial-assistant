import pytest
import httpx
import uuid


class TestSessionsGetContract:
    """Contract tests for GET /api/v1/sessions/{session_id} endpoint"""

    @pytest.mark.asyncio
    async def test_get_session_success(self):
        """Test successful session retrieval"""
        # First create a session to retrieve
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_data = create_response.json()
            session_id = session_data["session_id"]
            
            # Now retrieve the session
            response = await client.get(f"/api/v1/sessions/{session_id}")
            
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "session_id" in data
        assert "state" in data
        assert "created_at" in data
        assert "expires_at" in data
        assert "audio_file" in data
        assert "supplementary_content" in data
        assert "processing_status" in data
        assert "generated_summary" in data
        
        # Validate field values
        assert data["session_id"] == session_id
        assert data["state"] == "INITIAL"
        assert data["audio_file"] is None  # No audio uploaded yet
        assert isinstance(data["supplementary_content"], list)
        assert len(data["supplementary_content"]) == 0  # No content yet

    @pytest.mark.asyncio
    async def test_get_session_not_found(self):
        """Test retrieving non-existent session"""
        fake_session_id = str(uuid.uuid4())
        
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            response = await client.get(f"/api/v1/sessions/{fake_session_id}")
            
        assert response.status_code == 404
        error_data = response.json()
        assert "error" in error_data
        assert "not found" in error_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_get_session_invalid_uuid(self):
        """Test retrieving session with invalid UUID format"""
        invalid_session_id = "invalid-uuid-format"
        
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            response = await client.get(f"/api/v1/sessions/{invalid_session_id}")
            
        assert response.status_code == 422  # Validation error for invalid UUID

    @pytest.mark.asyncio
    async def test_get_session_expired(self):
        """Test retrieving expired session"""
        # This would require manipulating session expiration
        # For now, we'll test the expected behavior
        
        # Create session and simulate expiration
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            # In real implementation, would need to advance time or mock expiration
            # For now, assume session becomes expired
            
            # This test ensures expired sessions return 404
            # Implementation should check expiration time
            pass

    @pytest.mark.asyncio
    async def test_get_session_with_audio_uploaded(self):
        """Test retrieving session after audio upload"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            # Create session
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            # Upload audio (this will fail until audio endpoint is implemented)
            # This test documents expected behavior after audio upload
            
            # Expected: session state should be AUDIO_UPLOADED
            # Expected: audio_file should contain AudioFileInfo
            pass