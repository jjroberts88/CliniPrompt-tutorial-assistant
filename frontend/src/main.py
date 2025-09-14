import streamlit as st
import requests
import json
from datetime import datetime
from typing import Optional, Dict, Any


# Configuration
API_BASE_URL = "http://localhost:8001/api/v1"


def main():
    """Main Streamlit application"""
    st.set_page_config(
        page_title="ClinIPrompt Tutorial Assistant",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🏥 ClinIPrompt Tutorial Assistant")
    st.markdown("Transform clinical tutorial conversations into engaging podcast-style audio summaries")
    
    # Initialize session state
    if 'session_id' not in st.session_state:
        st.session_state.session_id = None
    if 'session_data' not in st.session_state:
        st.session_state.session_data = None
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = None
    
    # Sidebar for session management
    with st.sidebar:
        st.header("Session Management")
        
        # Create new session
        if st.button("🆕 Create New Session", type="primary"):
            create_new_session()
        
        # Show current session info
        if st.session_state.session_id:
            st.success(f"Session ID: {st.session_state.session_id[:8]}...")
            if st.button("🔄 Refresh Session"):
                refresh_session()
            if st.button("🗑️ End Session"):
                end_session()
        else:
            st.info("No active session")
    
    # Main content area
    if st.session_state.session_id:
        show_main_workflow()
    else:
        show_welcome_screen()


def show_welcome_screen():
    """Show welcome screen when no session is active"""
    st.markdown("""
    ## Welcome to ClinIPrompt Tutorial Assistant
    
    This tool helps you create engaging podcast-style summaries from clinical tutorial conversations.
    
    ### Features:
    - 🎵 **Audio Processing**: Upload clinical tutorial recordings (MP3, WAV, M4A, MP4)
    - 📄 **Content Enhancement**: Add PDFs and web links for comprehensive summaries
    - 🎯 **Customizable Duration**: Generate summaries from 10-30 minutes
    - 🔊 **High-Quality TTS**: Professional voice synthesis with medical terminology
    - 🏥 **Medical Focus**: Optimized for healthcare education content
    
    ### Getting Started:
    1. Click "Create New Session" in the sidebar
    2. Upload your clinical tutorial audio file
    3. Optionally add supplementary content (PDFs, web links)
    4. Configure your summary preferences
    5. Generate and download your podcast-style summary
    
    ### Requirements:
    - Audio files up to 30MB
    - Supported formats: MP3, WAV, M4A, MP4
    - Clear speech content for best results
    """)


def show_main_workflow():
    """Show main workflow interface"""
    if not st.session_state.session_data:
        refresh_session()
    
    session_data = st.session_state.session_data
    if not session_data:
        st.error("Failed to load session data")
        return
    
    # Show current session state
    state = session_data.get('state', 'UNKNOWN')
    st.info(f"Session State: **{state}**")
    
    # Step 1: Audio Upload
    st.header("🎵 Step 1: Upload Audio File")
    
    if state == "INITIAL":
        audio_file = st.file_uploader(
            "Upload clinical tutorial audio",
            type=['mp3', 'wav', 'm4a', 'mp4', 'ogg'],
            help="Maximum file size: 30MB. Supported formats: MP3, WAV, M4A, MP4, OGG"
        )
        
        if audio_file is not None:
            if st.button("📤 Upload Audio", type="primary"):
                upload_audio_file(audio_file)
    
    elif state in ["AUDIO_UPLOADED", "CONTENT_ADDED", "PROCESSING", "COMPLETED"]:
        st.success("✅ Audio file uploaded successfully")
        
        # Step 2: Optional Content Enhancement
        if state in ["AUDIO_UPLOADED", "CONTENT_ADDED"]:
            st.header("📄 Step 2: Add Supplementary Content (Optional)")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("PDF Documents")
                pdf_files = st.file_uploader(
                    "Upload PDF documents",
                    type=['pdf'],
                    accept_multiple_files=True,
                    help="Maximum 5 PDFs, 10MB each"
                )
                
                if pdf_files and st.button("📤 Upload PDFs"):
                    upload_pdf_files(pdf_files)
            
            with col2:
                st.subheader("Web References")
                web_links = st.text_area(
                    "Enter reference URLs (one per line)",
                    help="Maximum 10 URLs"
                )
                
                if web_links.strip() and st.button("🌐 Add Web Links"):
                    urls = [url.strip() for url in web_links.split('\n') if url.strip()]
                    add_web_links(urls)
        
        # Step 3: Processing Configuration
        if state in ["AUDIO_UPLOADED", "CONTENT_ADDED"]:
            st.header("⚙️ Step 3: Configure Processing")
            
            col1, col2 = st.columns(2)
            
            with col1:
                duration = st.slider(
                    "Summary Duration (minutes)",
                    min_value=10,
                    max_value=30,
                    value=20,
                    help="Desired length of the final summary"
                )
                
                focus_areas = st.multiselect(
                    "Focus Areas",
                    ["Key Learning Points", "Clinical Applications", "Case Studies", "Evidence-Based Practice"],
                    default=["Key Learning Points"],
                    help="Areas to emphasize in the summary"
                )
            
            with col2:
                voice_style = st.selectbox(
                    "Voice Style",
                    ["professional_female", "professional_male", "conversational_female", "conversational_male"],
                    help="Voice style for the generated audio"
                )
                
                summary_style = st.selectbox(
                    "Summary Style",
                    ["conversational", "technical", "basic"],
                    help="Overall style of the summary content"
                )
            
            custom_instruction = st.text_area(
                "Custom Instructions (Optional)",
                help="Additional instructions for content generation"
            )
            
            if st.button("🚀 Start Processing", type="primary"):
                start_processing(duration, focus_areas, voice_style, summary_style, custom_instruction)
        
        # Step 4: Processing Status
        if state == "PROCESSING":
            st.header("⏳ Processing Your Tutorial")
            
            # Auto-refresh processing status
            if st.button("🔄 Refresh Status"):
                check_processing_status()
            
            if st.session_state.processing_status:
                status = st.session_state.processing_status
                progress = status.get('progress', 0)
                current_step = status.get('current_step', 'Processing...')
                
                st.progress(progress / 100.0)
                st.info(f"Status: {current_step} ({progress}%)")
                
                if status.get('status') == 'error':
                    st.error(f"Processing failed: {status.get('error', 'Unknown error')}")
        
        # Step 5: Results
        if state == "COMPLETED":
            st.header("🎉 Summary Complete!")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 View Summary Script"):
                    show_summary_script()
            
            with col2:
                if st.button("🎵 Download Audio"):
                    download_audio()


def create_new_session():
    """Create a new session"""
    try:
        response = requests.post(f"{API_BASE_URL}/sessions")
        if response.status_code == 201:
            data = response.json()
            st.session_state.session_id = data['session_id']
            st.session_state.session_data = data
            st.success("New session created successfully!")
            st.rerun()
        else:
            st.error(f"Failed to create session: {response.text}")
    except requests.RequestException as e:
        st.error(f"Network error: {str(e)}")


def refresh_session():
    """Refresh current session data"""
    if not st.session_state.session_id:
        return
    
    try:
        response = requests.get(f"{API_BASE_URL}/sessions/{st.session_state.session_id}")
        if response.status_code == 200:
            st.session_state.session_data = response.json()
        else:
            st.error(f"Failed to refresh session: {response.text}")
    except requests.RequestException as e:
        st.error(f"Network error: {str(e)}")


def end_session():
    """End current session"""
    if not st.session_state.session_id:
        return
    
    try:
        response = requests.delete(f"{API_BASE_URL}/sessions/{st.session_state.session_id}")
        if response.status_code == 204:
            st.session_state.session_id = None
            st.session_state.session_data = None
            st.session_state.processing_status = None
            st.success("Session ended successfully!")
            st.rerun()
        else:
            st.error(f"Failed to end session: {response.text}")
    except requests.RequestException as e:
        st.error(f"Network error: {str(e)}")


def upload_audio_file(audio_file):
    """Upload audio file"""
    try:
        files = {"audio_file": (audio_file.name, audio_file.getvalue(), audio_file.type)}
        response = requests.post(
            f"{API_BASE_URL}/sessions/{st.session_state.session_id}/audio",
            files=files
        )
        
        if response.status_code == 201:
            st.success("Audio file uploaded successfully!")
            refresh_session()
            st.rerun()
        else:
            st.error(f"Failed to upload audio: {response.text}")
    except requests.RequestException as e:
        st.error(f"Network error: {str(e)}")


def upload_pdf_files(pdf_files):
    """Upload PDF files"""
    try:
        files = [("pdf_files", (pdf.name, pdf.getvalue(), pdf.type)) for pdf in pdf_files]
        response = requests.post(
            f"{API_BASE_URL}/sessions/{st.session_state.session_id}/pdfs",
            files=files
        )
        
        if response.status_code == 201:
            st.success("PDF files uploaded successfully!")
            refresh_session()
        else:
            st.error(f"Failed to upload PDFs: {response.text}")
    except requests.RequestException as e:
        st.error(f"Network error: {str(e)}")


def add_web_links(urls):
    """Add web reference links"""
    try:
        data = {"urls": urls}
        response = requests.post(
            f"{API_BASE_URL}/sessions/{st.session_state.session_id}/web-links",
            json=data
        )
        
        if response.status_code == 201:
            st.success("Web links added successfully!")
            refresh_session()
        else:
            st.error(f"Failed to add web links: {response.text}")
    except requests.RequestException as e:
        st.error(f"Network error: {str(e)}")


def start_processing(duration, focus_areas, voice_style, summary_style, custom_instruction):
    """Start processing the tutorial"""
    try:
        data = {
            "summary_duration": duration,
            "focus_areas": focus_areas,
            "voice_style": voice_style,
            "summary_style": summary_style
        }
        
        if custom_instruction.strip():
            data["custom_prompts"] = {
                "system_instruction": custom_instruction.strip()
            }
        
        response = requests.post(
            f"{API_BASE_URL}/sessions/{st.session_state.session_id}/process",
            json=data
        )
        
        if response.status_code == 202:
            st.success("Processing started successfully!")
            refresh_session()
            st.rerun()
        else:
            st.error(f"Failed to start processing: {response.text}")
    except requests.RequestException as e:
        st.error(f"Network error: {str(e)}")


def check_processing_status():
    """Check processing status"""
    try:
        response = requests.get(f"{API_BASE_URL}/sessions/{st.session_state.session_id}/status")
        if response.status_code == 200:
            st.session_state.processing_status = response.json()
            refresh_session()
        else:
            st.error(f"Failed to check status: {response.text}")
    except requests.RequestException as e:
        st.error(f"Network error: {str(e)}")


def show_summary_script():
    """Show the generated summary script"""
    st.info("Summary script display not yet implemented - requires backend processing completion")


def download_audio():
    """Download the generated audio"""
    st.info("Audio download not yet implemented - requires backend processing completion")


if __name__ == "__main__":
    main()