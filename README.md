# Voice Assistant – OpenAI Mahindra Edition

A web-based, real-time AI voice assistant for Mahindra vehicle guidance, powered by OpenAI and Django.

---

## Features

- **Voice Chat:** Speak directly to "Ishmael," a smart Mahindra sales consultant, via your browser.
- **Live Recommendations:** Get custom vehicle recommendations based on your needs, budget, and preferences.
- **Automatic Analytics:** Extracts your interests, preferences, and conversation summary as you chat.
- **Simple API:** RESTful endpoints for messages, session handling, analytics, and summaries.
- **Full-stack Solution:** Django backend, HTML + WebRTC frontend; easy to run on your machine.

---

## Quick Start

1. **Set Environment Variables:**  
   Create `.env` in the project root:
   ```
   OPENAI_API_KEY=sk-...
   SECRET_KEY=...
   DEBUG=True
   ```
2. **Install Dependencies:**  
   ```
   pip install -r requirements.txt
   ```
3. **Migrate Database:**  
   ```
   python manage.py makemigrations
   python manage.py migrate
   ```
4. **Run the App:**  
   ```
   start.bat          # (Windows 1-click)
   # OR
   python manage.py runserver
   ```
5. Access `[http://127.0.0.1:8000](http://127.0.0.1:8000)` in your browser.

---

## Architecture

- **Backend:** Django, OpenAI (GPT/Whisper), custom analyzer and models.
- **Frontend:** HTML, JavaScript, WebRTC voice streaming.
- **Data:** SQLite (dev), ready for PostgreSQL.

---

## System Instructions

Your assistant’s behavior is governed by the `system_instructions.md` file in the project root.  
**To customize how the agent behaves** (i.e., its personality, product knowledge, and sales logic), simply edit this Markdown file to match your use case.  
For example, update:
- Brand persona, tone, and allowed responses.
- Product lineup, frequently asked questions, etc.

This enables you to easily adapt the AI's personality or usage (e.g., use it for another brand, support other languages, etc.), without needing to change the code.

---

## File Overview

- `assistant/analyzer.py`: Extracts user info, intent, and preferences for smarter replies.
- `assistant/views.py`: Handles API and user interaction logic.
- `assistant/models.py`: Defines storage for conversations and related data.
- `assistant/urls.py`: API routing.
- `constants.py`: Loads system instructions, config, and OpenAI settings.
- `static/`: Frontend files (HTML, JS, CSS for the voice interface).
- `system_instructions.md`: Edit this as described above for your scenario.

---

## Key Endpoints

- `POST /api/session` : Start a new chat session.
- `POST /api/conversation` : Add a chat message.
- `POST /api/analysis` : Extract intelligence from the session.
- `GET /api/get-summary/<session_id>` : Get a conversation summary.
- `GET /api/get-recommendations` : Get vehicle suggestions.

---

## Troubleshooting

- Check `.env` content, and OpenAI key.
- Check Django logs for errors.
- All business behavior is controlled by `system_instructions.md`—edit this file to fit your application.

---

## Credits

Built by Techjays Intern Projects Team using Django and OpenAI.
Mahindra branding is for demonstration and learning only.

---