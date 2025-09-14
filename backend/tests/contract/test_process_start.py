import pytest
import httpx
import uuid


class TestProcessStartContract:
    """Contract tests for POST /api/v1/sessions/{session_id}/process endpoint"""

    @pytest.mark.asyncio
    async def test_start_processing_success(self):
        """Test successful processing initiation"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            # Create session and upload audio
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            # Mock audio upload (would need actual implementation)
            # For contract test, assume audio is uploaded
            
            # Start processing
            response = await client.post(
                f"/api/v1/sessions/{session_id}/process",
                json={
                    "summary_duration": 15,
                    "focus_areas": ["Key Learning Points", "Clinical Applications"],
                    "custom_prompts": {
                        "system_instruction": "Focus on practical applications",
                        "style_preferences": "conversational tone"
                    }
                }
            )
            
        assert response.status_code == 202
        data = response.json()
        
        # Validate response structure
        assert "task_id" in data
        assert "session_state" in data
        assert "estimated_completion" in data
        
        # Validate field types and values
        assert isinstance(data["task_id"], str)
        assert data["session_state"] == "PROCESSING"
        assert data["task_id"]  # Should not be empty

    @pytest.mark.asyncio
    async def test_start_processing_minimal_request(self):
        """Test processing with minimal required parameters"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            response = await client.post(
                f"/api/v1/sessions/{session_id}/process",
                json={"summary_duration": 20}
            )
            
        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data

    @pytest.mark.asyncio
    async def test_start_processing_invalid_duration(self):
        """Test processing with invalid duration"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            # Duration below minimum (10)
            response = await client.post(
                f"/api/v1/sessions/{session_id}/process",
                json={"summary_duration": 5}
            )
            
        assert response.status_code == 400
        error_data = response.json()
        assert "duration" in error_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_start_processing_duration_above_maximum(self):
        """Test processing with duration above maximum"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            # Duration above maximum (30)
            response = await client.post(
                f"/api/v1/sessions/{session_id}/process",
                json={"summary_duration": 35}
            )
            
        assert response.status_code == 400
        error_data = response.json()
        assert "duration" in error_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_start_processing_session_not_ready(self):
        """Test processing when session is not ready (no audio)"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            # Try to process without uploading audio
            response = await client.post(
                f"/api/v1/sessions/{session_id}/process",
                json={"summary_duration": 15}
            )
            
        assert response.status_code == 409
        error_data = response.json()
        assert "not ready" in error_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_start_processing_already_processing(self):
        """Test starting processing when already in progress"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            create_response = await client.post("/api/v1/sessions")
            session_id = create_response.json()["session_id"]
            
            # Mock session with audio and start first processing
            # This would require session to be in AUDIO_UPLOADED state
            
            # First processing request
            first_response = await client.post(
                f"/api/v1/sessions/{session_id}/process",
                json={"summary_duration": 15}
            )
            
            # Second processing request while first is running
            second_response = await client.post(
                f"/api/v1/sessions/{session_id}/process",
                json={"summary_duration": 20}
            )
            
        # Should prevent duplicate processing
        assert second_response.status_code == 409
        error_data = second_response.json()
        assert "already processing" in error_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_start_processing_invalid_session(self):
        """Test processing with non-existent session"""
        fake_session_id = str(uuid.uuid4())
        
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            response = await client.post(
                f"/api/v1/sessions/{fake_session_id}/process",
                json={"summary_duration": 15}
            )
            
        assert response.status_code == 404
        error_data = response.json()
        assert "not found" in error_data["error"]["message"].lower()