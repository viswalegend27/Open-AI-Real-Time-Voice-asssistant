# Voice Assistant – OpenAI Mahindra Edition

A web-based, real-time AI voice assistant for Mahindra vehicle guidance, powered by OpenAI and Django.

---

## Features

- **Voice Chat:** Speak directly to “Ishmael,” your smart Mahindra sales consultant, through the browser.
- **Live Recommendations:** Get personalized vehicle recommendations based on your needs, budget, and preferences.
- **On-the-Fly Analytics:** The assistant analyzes your conversation and extracts valuable interests and preferences while you chat.
- **Simple REST API:** Endpoints for chat interaction, session management, analytics, summaries, and more.
- **Complete Solution:** Django-powered backend; HTML, JS, and WebRTC frontend for cross-platform access.
- **Background Jobs:** Email notifications and summaries via automated background tasks.
- **Easily Customizable Persona:** Adapt the assistant's knowledge and character using a markdown config file.

---

## Quick Start

1. **Setup Environment Variables:**  
   Copy `.env_example.txt` to `.env` and fill in your OpenAI, database, and email details.
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
5. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Configuration & Customization

- **Environment Setup:**  
  Use the `.env_example.txt` as a template for your secret keys, database settings, and email credentials. Make sure your real `.env` is never shared publicly!

- **Behavior & Personality:**  
  The assistant’s tone, product knowledge, and logic live in `system_instructions.md`. Edit this file to adapt the voice assistant for different products, brands, behaviors, or languages without changing any Python code.

- **Email & Background Tasks:**  
  The assistant can email conversation summaries and reports using your SMTP settings.

---

## API Endpoints

- `POST /api/session` : Start a new chat session (creates an OpenAI session).
- `POST /api/conversation` : Add and receive chat messages.
- `POST /api/analysis` : Extract analytics and insights from a chat session.

---

## Backend Highlights

- **Django App:** Handles chat, user context, analytics, and integrations.
- **OpenAI Integration:** Live interaction with OpenAI's GPT and Whisper APIs.
- **PostgreSQL Database:** Secure storage for sessions and conversation data.
- **Celery Tasks:** Schedules summarization and email delivery in the background.
- **Celery Beat Scheduler:** Would run every 20 seconds to schedule my email. Provide 1 email per-conversation
- **Easily Extended:** Add tools, analysis logic, or API capabilities to the project by expanding the `assistant/` module.

---

## Frontend Highlights

- **Browser Voice Chat:** Real-time voice interface using JavaScript, HTML, CSS, and WebRTC.
- **Easy to Use:** Simple, modern interface to engage with the AI assistant—no plugins required.

---

## Customizing System Instructions

- Update `system_instructions.md` to adjust personality, conversation rules, FAQ lists, product details, or any brand requirements.
- This file is all you need to edit to repurpose the AI for a new domain or language!

---

## Troubleshooting

- Double-check your `.env` for correct OpenAI, DB, and email settings.
- Inspect Django and Celery logs for error details.
- If the assistant's replies are not as expected, review and adjust `system_instructions.md`.
- For frontend issues, use browser dev tools (console/network).

---

## Credits

Built by the Techjays Intern Projects Team using Django and OpenAI.
Mahindra branding is for demonstration and learning only.

---
