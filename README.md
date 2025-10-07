# Mahindra Voice Assistant💥🚗

[EXPERIMENTAL PROJECT] 

---

## Disclaimer

**This project is experimental and not production-ready. Use at your own risk. There may be bugs, incomplete features, or unstable behavior.**  
For learning, prototyping, and internal demo purposes only.

---

## Overview

"Ishmael" is a real-time voice assistant designed for Mahindra Automotive sales consultation, powered by OpenAI’s GPT-4o and Whisper models.  
Users can speak to Ishmael through their browser, and receive friendly, consultative, and knowledgeable responses about Mahindra vehicles—instantly, by voice.

- **Live two-way voice conversation** (WebRTC streaming)
- **AI persona** tuned for Mahindra sales expertise
- **FastAPI backend with browser UI**
- **Modern, easy-to-use frontend** (works locally)
- **Transcription & TTS**: Uses OpenAI’s Whisper for transcription and GPT-based voice generation

---

## Features

- Real-time voice consultation with a Mahindra sales expert persona (“Ishmael”)
- Personalized vehicle recommendations and honest guidance
- Financing, offers, warranty, and general product queries supported
- Test drive scheduling assistance (informational)
- Friendly, consultative, and transparent communication style
- Clean local-first browser interface

---

## Quick Start

### 1. Clone & Prepare

```shell
git clone <your-repo-url>
cd Voice-assistant-using-Open-AI
```

### 2. Configure API Key

- Create a `.env` file in the root directory:

    ```
    OPENAI_API_KEY=sk-...
    ```

### 3. Install Requirements

**Windows:**
```shell
start_ishmael.bat
```

**Or manually:**
```shell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run the Server

```shell
python server_realtime.py
```

### 5. Open in Browser

Go to [http://127.0.0.1:8000](http://127.0.0.1:8000) in Chrome or Edge for the best experience.

---

## Project Structure

```
Voice-assistant-using-Open-AI/
│
├── constants.py              # All app settings, persona, and OpenAI constants
├── server_realtime.py        # FastAPI backend for browser-to-OpenAI realtime voice
├── requirements.txt          # Dependencies
├── static/
│   ├── index_new.html        # Modern Mahindra UI
│   ├── realtime.html         # (Optional/legacy) Old UI
│   ├── js/app.js             # Frontend logic (WebRTC, streaming, UI updates)
│   └── css/                  # Styling: Mahindra theme, Ishmael theme, etc.
├── start_ishmael.bat         # Windows quick-start script
├── .env                      # API credentials (not committed)
└── .gitignore
```

---

## How It Works

### Backend

- **FastAPI server (`server_realtime.py`)**
  - Serves the frontend and handles CORS/static files
  - `/session/` endpoint: Provisions an ephemeral OpenAI WebRTC session for the browser
  - Configures OpenAI model/voice according to environment or defaults
  - Health check endpoint `/health`

### Frontend

- **Modern HTML+JS UI (in `static/index_new.html` & `js/app.js`):**
  - Click “Start Conversation” to begin streaming live audio from your mic.
  - Browser connects directly to OpenAI with the session token.
  - Transcripts and Ishmael’s replies are shown in real time.
  - Ishmael’s spoken responses are streamed back using OpenAI TTS.

---

## Mahindra Sales AI Persona

“Ishmael” is a consultative, trusted Mahindra sales expert. They help you:

- Choose between Mahindra SUVs, EVs, and commercial vehicles
- Compare features, pricing, and financing options
- Schedule test drives and get dealership details
- Understand after-sales service benefits
- Answer common customer questions transparently

---

## Tech Stack

- Python 3.8+
- FastAPI
- httpx, python-dotenv
- OpenAI API (GPT-4o, Whisper, TTS)
- WebRTC for real-time browser ↔️ OpenAI voice streaming
- Frontend: HTML/CSS/JS (vanilla), custom Mahindra branding

---

## Requirements

- Python 3.8+ (Windows recommended for the .bat script; works on Mac/Linux with tweaks)
- Chrome or Edge for best WebRTC and audio support
- A valid OpenAI API key with GPT-4o, Whisper, and Voice API access

---

## Setup Troubleshooting

- Ensure your OpenAI account enables voice and real-time API beta features.
- If you have audio device issues, check browser permissions and try another browser.
- If you see errors related to missing .env, virtual environment, or packages, run the startup steps manually.

---

## Roadmap / Known Issues

- This is a research experiment; features and flow may change without notice
- Not tested for heavy workloads or concurrent users
- Minimal security, scalability, or error handling (do **not** run on public servers)
- Feedback and contributions are welcome for learning purposes

---

## Credits

- Built by Techjays Intern Projects Team  
- Powered by [OpenAI API](https://platform.openai.com/)
- Mahindra branding and vehicle information are for demonstration purposes only

---

**Enjoy your Mahindra sales experience with Ishmael! 🚙💨**
