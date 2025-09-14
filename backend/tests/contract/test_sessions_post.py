import pytest
import httpx
from unittest.mock import patch


class TestSessionsPostContract:
    """Contract tests for POST /api/v1/sessions endpoint"""

    @pytest.mark.asyncio
    async def test_create_session_success(self):
        """Test successful session creation with valid request"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            response = await client.post(
                "/api/v1/sessions",
                json={
                    "user_agent": "Mozilla/5.0 (Test Browser)",
                    "preferences": {
                        "preferred_voice": "professional_female",
                        "summary_style": "conversational",
                        "emphasis_areas": ["Key Learning Points"]
                    }
                }
            )
            
        assert response.status_code == 201
        data = response.json()
        
        # Validate response structure
        assert "session_id" in data
        assert "state" in data
        assert "created_at" in data
        assert "expires_at" in data
        
        # Validate field types and values
        assert isinstance(data["session_id"], str)
        assert data["state"] == "INITIAL"
        assert data["session_id"]  # Should not be empty

    @pytest.mark.asyncio 
    async def test_create_session_minimal_request(self):
        """Test session creation with minimal request body"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            response = await client.post("/api/v1/sessions", json={})
            
        assert response.status_code == 201
        data = response.json()
        assert data["state"] == "INITIAL"

    @pytest.mark.asyncio
    async def test_create_session_invalid_preferences(self):
        """Test session creation with invalid preferences"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            response = await client.post(
                "/api/v1/sessions",
                json={
                    "preferences": {
                        "preferred_voice": "invalid_voice",
                        "summary_style": "invalid_style"
                    }
                }
            )
            
        assert response.status_code == 400
        error_data = response.json()
        assert "error" in error_data
        assert "code" in error_data["error"]
        assert "message" in error_data["error"]

    @pytest.mark.asyncio
    async def test_create_session_rate_limit(self):
        """Test session creation rate limiting (5 concurrent per IP)"""
        # This test simulates exceeding the concurrent session limit
        # In real implementation, would need to track IP addresses
        
        # Mock the rate limiting logic
        with patch('src.api.sessions.check_session_limit') as mock_limit:
            mock_limit.return_value = False  # Simulate limit exceeded
            
            async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
                response = await client.post("/api/v1/sessions")
                
            assert response.status_code == 429
            error_data = response.json()
            assert "Too many concurrent sessions" in error_data["error"]["message"]

    @pytest.mark.asyncio
    async def test_create_session_malformed_json(self):
        """Test session creation with malformed JSON"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            response = await client.post(
                "/api/v1/sessions",
                content='{"invalid": json',
                headers={"Content-Type": "application/json"}
            )
            
        assert response.status_code == 422  # Unprocessable Entity for malformed JSON