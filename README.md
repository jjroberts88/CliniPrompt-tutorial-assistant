# ClinIPrompt Tutorial Assistant

A medical tutorial processing application that converts clinical tutorial recordings into engaging podcast-style audio summaries using AI.

## Features

- 🎵 **Audio Processing**: Upload clinical tutorial recordings (MP3, WAV, M4A, MP4, OGG)
- 📄 **Content Enhancement**: Add PDFs and web links for comprehensive summaries
- 🎯 **Customizable Duration**: Generate summaries from 10-30 minutes
- 🔊 **High-Quality TTS**: Professional voice synthesis optimized for medical terminology
- 🏥 **Medical Focus**: Optimized for healthcare education content
- 📊 **Real-time Status**: Track processing progress with live updates

## Architecture

- **Backend**: FastAPI (Python) - REST API for session management and processing
- **Frontend**: Streamlit - Interactive web interface
- **AI Integration**: Google Gemini API (configuration ready)

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd cliniprompt-tutorial-assistant
   ```

2. **Backend Setup**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Frontend Setup**:
   ```bash
   cd ../frontend  
   pip install -r requirements.txt
   ```

4. **Environment Configuration** (Optional):
   ```bash
   cp backend/.env.example backend/.env
   # Edit .env with your Gemini API key and other settings
   ```

### Running the Application

1. **Start the Backend API** (in `backend/` directory):
   ```bash
   PYTHONPATH=/path/to/backend python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload
   ```

2. **Start the Frontend** (in `frontend/` directory):
   ```bash
   streamlit run src/main.py --server.port 8501
   ```

3. **Access the Application**:
   - Frontend: http://localhost:8501
   - Backend API: http://localhost:8001
   - API Documentation: http://localhost:8001/docs

## Usage

1. **Create a Session**: Click "Create New Session" in the sidebar
2. **Upload Audio**: Upload your clinical tutorial audio file (max 30MB)
3. **Add Content** (Optional): Upload PDFs or add web reference links
4. **Configure Processing**: Set duration, voice style, and focus areas
5. **Start Processing**: Generate your podcast-style summary
6. **Download Results**: Get your audio summary and script

## API Endpoints

- `POST /api/v1/sessions` - Create new session
- `GET /api/v1/sessions/{session_id}` - Get session details
- `DELETE /api/v1/sessions/{session_id}` - Delete session
- `POST /api/v1/sessions/{session_id}/audio` - Upload audio file
- `POST /api/v1/sessions/{session_id}/process` - Start processing
- `GET /api/v1/sessions/{session_id}/status` - Get processing status
- `GET /api/v1/health` - Health check

## Configuration

The application supports extensive configuration via environment variables. See `backend/.env.example` for all available options including:

- Gemini API settings
- Storage configurations
- Processing parameters
- API server settings

## Development Status

✅ **Complete**: Session management, file uploads, API endpoints, Streamlit UI  
🚧 **In Progress**: AI processing implementation (Gemini integration ready)  
📋 **Planned**: PDF processing, web content analysis, advanced TTS features

## Contributing

This is a medical education tool designed to help healthcare professionals create engaging content. Contributions focused on improving medical terminology handling, accessibility, and educational effectiveness are welcome.

## License

[Add your license here]