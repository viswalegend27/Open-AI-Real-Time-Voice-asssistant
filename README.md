# Mahindra Voice Assistant 🚗💨

**An intelligent, real-time AI voice consultation system for Mahindra automotive sales powered by OpenAI GPT-4o.**

This project delivers a web-based virtual sales consultant, "Ishmael", who guides customers with vehicle recommendations, real-time voice interaction, and conversation intelligence powered by OpenAI and Django.

---

## ✨ Features

- **Real-time voice consultation** with AI through browser & OpenAI streaming (WebRTC audio)
- **Personalized Mahindra vehicle recommendations** based on customer conversation and preferences
- **Automatic intelligence extraction** (budget, use-case, preferences, intent, features)
- **Persistent session and database storage** for conversations and extracted intelligence
- **Conversation summaries** and analytics (sentiment, engagement, purchase signals)
- **RESTful API endpoints** for frontend/backend/data/AI integrations

---

## 🏗️ Architecture Overview

- **Backend:** Django (Python), SQLite (dev) / PostgreSQL (prod)
- **AI/Intelligence:** OpenAI GPT-4o for conversation, Whisper STT, TTS, and custom analyzer
- **Frontend:** HTML/JS, static assets, WebRTC streaming for low-latency voice communication

---

## 📦 Main Code Modules & Their Roles

### Module Highlights

- **assistant/analyzer.py**
  - Extracts budget, use-case, and interests from messages
  - Computes AI-based Mahindra vehicle recommendations
  - Generates AI-powered conversation summaries (via OpenAI or rule-based fallback)
  - Formats and saves intelligence to DB for analytics & follow-up

- **assistant/models.py**
  - `Conversation`: Tracks sessions and core metadata
  - `Message`: Stores each chat utterance (AI/user, timestamp)
  - `UserPreference`, `VehicleInterest`: Structured intelligence extraction from chats
  - `Recommendation`: System recommendations per session/criteria
  - `ConversationSummary`: AI-generated summary and key engagement/insights

- **assistant/views.py**
  - REST endpoints for:
    - Session handling (`/api/session`)
    - Saving/getting messages and intelligence
    - Retrieving/triggering recommendations, summaries, analytics
    - Base health check (`/health`)

- **constants.py**
  - Persona description, system prompt, OpenAI model settings, tool/function configs
  - Helper functions for OpenAI session setup

- **static/js/app.js**
  - Handles user push-to-talk, streaming audio, frontend API interaction

---

## 🗄️ Database Models

- **Conversation:** Session info (user, timestamps, total messages)
- **Message:** Every utterance in a session; role ("user"/"assistant"), timestamp
- **UserPreference:** Extracted info (budget, use-case, etc.) with type/confidence
- **VehicleInterest:** Tracks interest intensity for Mahindra vehicles
- **Recommendation:** System-generated recommendations with reasons, scores
- **ConversationSummary:** AI summary, engagement, customer/contact info, recommendations, next steps

---

## 🔌 API Endpoints

### Voice & Conversation
- `GET /` — Main web interface (serves HTML)
- `POST /api/session` — Create OpenAI Realtime Voice/AI session
- `POST /api/conversations/` — Start new customer conversation
- `POST /api/conversations/<id>/messages/` — Save new message to conversation
- `POST /api/analyze-conversation/` — Trigger intelligence extraction

### Intelligence & Analytics
- `GET /api/conversations/<id>/intelligence/` — Get extracted preferences, budget, etc.
- `GET /api/conversations/<id>/recommendations/` — AI vehicle recommendations for that session
- `POST /api/generate-summary/` — Generate summary and key details for a conversation
- `GET /api/conversations/<id>/summary/` — Retrieve saved summary

### Health & Utility
- `GET /health` — Health check endpoint

---

## 🚀 Quick Start

1. **Configure Env** (`.env`):
   ```
   OPENAI_API_KEY=sk-proj-XXX
   SECRET_KEY=django-secret-XXX
   DEBUG=True
   ```
2. **Install dependencies**:  
   `pip install -r requirements.txt`
3. **Initialize DB**:  
   `python manage.py makemigrations && python manage.py migrate`
4. **Run server**:
   - `start.bat` (Windows, one-click)  
   - OR: `python manage.py runserver`
5. Open browser at http://127.0.0.1:8000 and start conversing!

---

## 🧠 Intelligence Extraction Logic

- Extracts: budget (e.g., "20 lakhs"), use case ("family"/"adventure"/"city"), vehicles of interest (Thar, XUV700, Scorpio, etc.)
- Updates model scores for recommendation
- Summarizes with key customer data, priorities, intent, engagement, and suggested next steps (sales follow-up)

---

## 🛠️ Tech Stack

- Django 4.x, python-dotenv, httpx, CORS
- OpenAI GPT-4o API (real time), Whisper STT, custom AI analyzer
- WebRTC, HTML/JS/CSS frontend
- SQLite (dev), PostgreSQL (prod-ready)

---

## 🔧 Configuration

All configurable values and system prompts stored in `constants.py` and `.env`.

---

## 👤 Credits

By Techjays Intern Projects Team.  
Powered by OpenAI GPT-4o and Django.

Mahindra branding is for internal/educational demonstration only.

---

## 📞 Support & Troubleshooting

See "Troubleshooting" and "Testing" in this README.  
For major issues: check `.env` variables, API key, DB migrations, or contact the team directly.