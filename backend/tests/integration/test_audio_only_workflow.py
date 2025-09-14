import pytest
import httpx
import asyncio
from pathlib import Path
import os


class TestAudioOnlyWorkflow:
    """Integration test for complete audio-only processing workflow"""

    @pytest.fixture
    def sample_audio_file(self):
        """Sample audio file for testing"""
        # Create a minimal MP3 file for testing
        audio_data = b"ID3\x03\x00\x00\x00" + b"\x00" * 5000  # ~5KB audio file
        return ("sample-tutorial.mp3", audio_data, "audio/mpeg")

    @pytest.mark.asyncio
    async def test_complete_audio_workflow(self, sample_audio_file):
        """Test complete workflow with audio file only"""
        async with httpx.AsyncClient(
            base_url="http://localhost:8000", 
            timeout=300.0  # 5 minutes for processing
        ) as client:
            
            # Step 1: Create session
            response = await client.post(
                "/api/v1/sessions",
                json={
                    "preferences": {
                        "preferred_voice": "professional_female",
                        "summary_style": "conversational"
                    }
                }
            )
            assert response.status_code == 201
            session_data = response.json()
            session_id = session_data["session_id"]
            assert session_data["state"] == "INITIAL"
            
            # Step 2: Upload audio
            filename, audio_data, mime_type = sample_audio_file
            files = {"audio_file": (filename, audio_data, mime_type)}
            response = await client.post(
                f"/api/v1/sessions/{session_id}/audio",
                files=files
            )
            assert response.status_code == 201
            upload_data = response.json()
            assert upload_data["session_state"] == "AUDIO_UPLOADED"
            
            # Validate audio file info
            file_info = upload_data["file_info"]
            assert file_info["file_name"] == filename
            assert file_info["mime_type"] == mime_type
            assert file_info["file_size_mb"] > 0
            
            # Step 3: Start processing
            response = await client.post(
                f"/api/v1/sessions/{session_id}/process",
                json={
                    "summary_duration": 10,
                    "focus_areas": ["Key Learning Points"]
                }
            )
            assert response.status_code == 202
            process_data = response.json()
            task_id = process_data["task_id"]
            assert process_data["session_state"] == "PROCESSING"
            
            # Step 4: Wait for completion
            max_wait_time = 300  # 5 minutes maximum
            poll_interval = 5  # Poll every 5 seconds
            processing_complete = False
            
            for _ in range(max_wait_time // poll_interval):
                response = await client.get(f"/api/v1/sessions/{session_id}/status")
                assert response.status_code == 200
                status_data = response.json()
                
                assert status_data["task_id"] == task_id
                assert "status" in status_data
                assert "progress" in status_data
                assert "current_step" in status_data
                
                if status_data["status"] == "completed":
                    processing_complete = True
                    assert status_data["progress"] == 100
                    break
                elif status_data["status"] == "error":
                    pytest.fail(f"Processing failed: {status_data.get('error', 'Unknown error')}")
                else:
                    # Still processing
                    assert status_data["status"] in ["pending", "processing"]
                    assert 0 <= status_data["progress"] <= 100
                
                await asyncio.sleep(poll_interval)
            
            if not processing_complete:
                pytest.fail("Processing timeout - did not complete within 5 minutes")
            
            # Step 5: Verify session state
            response = await client.get(f"/api/v1/sessions/{session_id}")
            assert response.status_code == 200
            session_detail = response.json()
            assert session_detail["state"] == "COMPLETED"
            
            # Step 6: Retrieve summary
            response = await client.get(f"/api/v1/sessions/{session_id}/summary")
            assert response.status_code == 200
            summary_data = response.json()
            
            # Validate summary structure
            assert "summary_info" in summary_data
            assert "script_content" in summary_data
            assert "audio_download_url" in summary_data
            
            # Validate summary info
            summary_info = summary_data["summary_info"]
            assert "summary_id" in summary_info
            assert "actual_duration" in summary_info
            assert "requested_duration" in summary_info
            assert "generation_timestamp" in summary_info
            assert "quality_metrics" in summary_info
            assert "source_analysis" in summary_info
            
            # Validate duration accuracy (within 20% tolerance)
            actual_duration = summary_info["actual_duration"]
            requested_duration = summary_info["requested_duration"]
            assert requested_duration == 10
            tolerance = requested_duration * 0.2
            assert abs(actual_duration - requested_duration) <= tolerance
            
            # Validate content quality
            assert len(summary_data["script_content"]) > 500  # Substantial content
            assert "clinical" in summary_data["script_content"].lower() or \
                   "medical" in summary_data["script_content"].lower()
            
            # Validate quality metrics
            quality_metrics = summary_info["quality_metrics"]
            assert 0.0 <= quality_metrics.get("medical_accuracy", 0) <= 1.0
            assert 0.0 <= quality_metrics.get("content_coherence", 0) <= 1.0
            assert 0.0 <= quality_metrics.get("educational_value", 0) <= 1.0
            
            # Step 7: Download audio
            response = await client.get(f"/api/v1/sessions/{session_id}/audio-download")
            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/mpeg"
            assert len(response.content) > 50000  # Reasonable audio file size for 10 minutes
            
            # Validate audio file headers
            audio_content = response.content
            assert audio_content.startswith(b"ID3") or audio_content.startswith(b"\xff")  # MP3 headers
            
            # Step 8: Cleanup (optional - should auto-expire)
            response = await client.delete(f"/api/v1/sessions/{session_id}")
            assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_workflow_with_different_durations(self, sample_audio_file):
        """Test workflow with different summary durations"""
        durations_to_test = [10, 15, 20, 25, 30]
        
        for target_duration in durations_to_test:
            async with httpx.AsyncClient(
                base_url="http://localhost:8000", 
                timeout=360.0  # 6 minutes for longer summaries
            ) as client:
                
                # Create fresh session
                response = await client.post("/api/v1/sessions")
                session_id = response.json()["session_id"]
                
                # Upload audio
                filename, audio_data, mime_type = sample_audio_file
                files = {"audio_file": (filename, audio_data, mime_type)}
                await client.post(f"/api/v1/sessions/{session_id}/audio", files=files)
                
                # Process with specific duration
                await client.post(
                    f"/api/v1/sessions/{session_id}/process",
                    json={"summary_duration": target_duration}
                )
                
                # Wait for completion (simplified polling)
                for _ in range(72):  # 6 minutes max
                    await asyncio.sleep(5)
                    status_response = await client.get(f"/api/v1/sessions/{session_id}/status")
                    if status_response.json()["status"] == "completed":
                        break
                
                # Verify duration accuracy
                summary_response = await client.get(f"/api/v1/sessions/{session_id}/summary")
                if summary_response.status_code == 200:
                    summary_info = summary_response.json()["summary_info"]
                    actual_duration = summary_info["actual_duration"]
                    tolerance = target_duration * 0.2  # 20% tolerance
                    assert abs(actual_duration - target_duration) <= tolerance

    @pytest.mark.asyncio
    async def test_workflow_error_recovery(self):
        """Test workflow error handling and recovery"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            
            # Test with invalid audio data
            response = await client.post("/api/v1/sessions")
            session_id = response.json()["session_id"]
            
            # Upload corrupted audio
            corrupted_audio = b"not_actually_audio_data"
            files = {"audio_file": ("corrupted.mp3", corrupted_audio, "audio/mpeg")}
            
            # Upload might succeed but processing should fail gracefully
            upload_response = await client.post(
                f"/api/v1/sessions/{session_id}/audio",
                files=files
            )
            
            if upload_response.status_code == 201:
                # Try to process corrupted audio
                process_response = await client.post(
                    f"/api/v1/sessions/{session_id}/process",
                    json={"summary_duration": 10}
                )
                
                if process_response.status_code == 202:
                    # Wait for processing to fail
                    await asyncio.sleep(30)
                    
                    status_response = await client.get(f"/api/v1/sessions/{session_id}/status")
                    status_data = status_response.json()
                    
                    # Should either be in error state or have failed gracefully
                    if status_data["status"] == "error":
                        assert "error" in status_data
                        assert len(status_data["error"]) > 0