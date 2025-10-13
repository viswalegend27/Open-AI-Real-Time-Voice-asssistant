# Mahindra Voice Assistant 🚗💨

**An intelligent, real-time AI voice consultation system for Mahindra automotive sales powered by OpenAI GPT-4o.**

This project delivers a web-based virtual sales consultant, "Ishmael," who guides customers with vehicle recommendations, real-time voice interaction, and conversation intelligence powered by OpenAI and Django.

---

## ✨ Current Features & Flow

- **Real-time voice AI consultation:** Audio streaming (WebRTC) lets users speak to the AI, which responds with natural voice using OpenAI and TTS models.
- **Personalized vehicle recommendations** computed live via AI and a hand-curated analyzer.
- **Automatic conversation intelligence extraction:** Session storage persists budget, use-case, features, interests, and sentiment per conversation.
- **Conversation summary and analytics:** Summaries, purchase intent, engagement, etc.
- **REST-style API endpoints** for all core operations, with separation of concerns between session setup, message handling, analytics, and recommendations.
- **Robust error handling** with JSON error responses and logging.

---

## 🏗️ Architecture Overview

- **Backend:** Django, httpx, dotenv (config), custom business logic in `analyzer.py`, data in `models.py`.
- **AI/Intelligence:** GPT-4o (OpenAI), Whisper, and custom analyzer for extracting actionable insights.
- **Frontend:** HTML, CSS, JS, with WebRTC for low-latency voice.
- **APIs:** `/api/session` for OpenAI stream setup, `/api/conversation`, `/api/analysis`, `/api/get-recommendations`, `/api/generate-summary`, etc.

---

## 📦 Main Code Modules & Their Roles

- **assistant/views.py**
  - Handles all API endpoint logic: session creation, saving messages, triggering analytics, summary creation and fetch, recommendations, and healthcheck.
  - Uses helpers for JSON error formatting and request de-serialization.
  - Calls into `analyzer.py` functions and models for all backend computation/storage.
  - Loads settings and secret keys using `.env` and `constants.py`.

- **assistant/analyzer.py**
  - Parses raw conversation and extracts intelligence (budget, features, interests, tone, sentiment, summary).
  - Provides rule-based and AI-powered recommendations, calls OpenAI as needed.
  - Business logic for customer engagement and purchase tracking.

- **assistant/models.py**
  - Defines schema for Conversation, Message, UserPreference, VehicleInterest, Recommendation, ConversationSummary for persistent storage of chats, extracted insights, and recommendations.

- **constants.py**
  - Stores all system-wide settings, OpenAI model and API config, persona/system prompts, and config helpers.

- **static/js/app.js**
  - Deals with audio capture, WebRTC streaming, push-to-talk interface, and frontend use of the API endpoints.

---

## 🗄️ Database Models

- **Conversation:** Session info, start/end, total messages.
- **Message:** Each chat utterance, AI/user role, timestamped.
- **UserPreference/VehicleInterest:** Info parsed from chat.
- **Recommendation:** Vehicle recommendations per session/criteria.
- **ConversationSummary:** Summarized chat, key extracted and computed info.

---

## 🔌 Core API Endpoints

| Endpoint                               | Function                                   |
|-----------------------------------------|--------------------------------------------|
| `GET /`                                | Main UI (HTML)                             |
| `POST /api/session`                    | OpenAI stream session creation             |
| `POST /api/conversation`               | Save a new message in the conversation     |
| `POST /api/analysis`                   | Run analytics/extract intelligence         |
| `POST /api/generate-summary`           | Generate and save conversation summary     |
| `GET /api/get-summary/<session_id>`    | Retrieve evidence summary (if exists)      |
| `GET /api/get-recommendations`         | Get recommended vehicles                   |
| `GET /health`                          | Service/agent health check                 |

---

## 🚀 Quick Start

1. **Configure your environment** (`.env`):
   ```
   OPENAI_API_KEY=sk-...
   SECRET_KEY=...
   DEBUG=True
   ```
2. **Install dependencies:**  
   `pip install -r requirements.txt`
3. **Run DB migrations:**  
   `python manage.py makemigrations && python manage.py migrate`
4. **Run server:**
   - `start.bat` (Windows, one-click)  
   - OR: `python manage.py runserver`
5. Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 🧠 How Intelligence Extraction Works

- As you converse, every message is saved, and relevant entities (budget, intent, preferences, etc.) are extracted by the analyzer.
- Recommendations run in real-time or on request, blending user signals and curated product data.
- Summaries merge all session data, provide next actions, engagement scores, and purchase likelihood.
- All key actions (save, analyze, recommend, summarize) are triggered by distinct endpoints.

---

## 🛠️ Tech Stack

- **Python:** Django 4+, httpx, python-dotenv.
- **AI:** OpenAI GPT-4o, Whisper, custom rules.
- **Frontend:** HTML/CSS/JS, WebRTC audio.
- **DB:** SQLite (dev) / PostgreSQL (during production).

---

## 🔧 Configuration

All config values (most prompts, model/voice names, endpoints, etc) are sourced from `constants.py` and `.env`.

---

## 👤 Credits

By Techjays Intern Projects Team.  
Powered by OpenAI GPT-4o and Django.  
Mahindra branding is for education/demo use only.

---

## 📞 Support & Troubleshooting

- Check `.env` values, OpenAI API key, and DB migrations.
- For code or logic errors, see logs (logging is built into all endpoints).
- Reach out to the team for advanced help.