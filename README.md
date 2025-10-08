# Mahindra Voice Assistant 🚗💨

**Real-time AI voice consultation for Mahindra automotive sales powered by OpenAI GPT-4o**

---

## Features

- Real-time voice consultation with Mahindra sales AI ("Ishmael")
- WebRTC audio streaming, browser-based interface
- Personalized vehicle recommendations
- Product knowledge, financing, and test drive assistance

---

## Quick Start

### 1. Setup Environment

Create `.env` file:
```
OPENAI_API_KEY=sk-your-key-here
```

### 2. Install & Run

**Option 1** (Easy):
```bash
start_ishmael.bat
```

**Option 2** (Manual):
```bash
pip install -r requirements.txt
python manage.py runserver
```

### 3. Open Browser

Navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000) and click "Start Conversation"

---

## Project Structure

```
project/
├── manage.py              # Django management
├── voice_assistant/       # Django config
├── assistant/             # Main app (views, URLs)
├── constants.py           # OpenAI config & AI persona
├── requirements.txt       # Dependencies
├── static/                # Frontend (HTML/CSS/JS)
├── start_ishmael.bat      # Startup script
└── .env                   # API key
```

## Endpoints

- `GET /` - Main interface
- `POST /api/session` - Create OpenAI session
- `GET /health` - Health check

---

## Tech Stack

- **Backend:** Django, Python 3.8+
- **AI:** OpenAI GPT-4o, Whisper, Realtime API
- **Frontend:** HTML/CSS/JS, WebRTC audio streaming
- **Dependencies:** httpx, python-dotenv, django-cors-headers

## Requirements

- Python 3.8+, Chrome/Edge browser
- OpenAI API key with GPT-4o and Voice API access

---

---

**Built by Techjays Intern Projects Team | Powered by OpenAI API**

*Note: Experimental project for learning purposes. Mahindra branding for demo only.*
