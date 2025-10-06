# Voice Assistant using OpenAI (FastAPI)

A simple **voice-to-voice assistant** built with **FastAPI** and **OpenAI’s GPT + speech models**.
🎤 Speak → 📝 Transcribe → 🤖 Chat → 🔊 Get a spoken reply.

---

## 🚀 Features

* 🎙️ **Record voice in browser** (via `MediaRecorder`)
* 📝 **Transcribe speech to text** using OpenAI

  * Default: `gpt-4o-transcribe` (best)
  * Fallback: `whisper-1`
* 🤖 **Chat reply** generated with `gpt-4o-mini`
* 🔊 **Text-to-speech** with `tts-1` (streamed back as MP3)
* 🌐 **FastAPI backend** with `/chat` endpoint
* 📄 Simple static frontend (`static/index.html`) to test recording & playback

---

## 🛠️ Tech Stack

* **Backend**: FastAPI, Uvicorn, OpenAI Python SDK
* **Frontend**: HTML + JavaScript (MediaRecorder API)
* **Other**: dotenv (for API key management), CORS support

---

## ⚙️ Setup

### 1. Clone & enter project

```bash
git clone <your-repo-url>
cd Voice-assistant-using-Open-AI
```

### 2. Create virtual environment

```bash
python -m venv venv
# activate venv
# On Windows (PowerShell):
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your OpenAI API Key

Create a `.env` file in the root:

```
OPENAI_API_KEY=sk-your-real-key-here
```

---

## ▶️ Run the server

```bash
uvicorn server:app --reload
```

Server runs at: [http://127.0.0.1:8000](http://127.0.0.1:8000)

* `GET /` → loads `static/index.html`
* `POST /chat` → accepts an audio file, returns spoken reply

---

## 🎤 Usage

1. Open `http://127.0.0.1:8000/` in your browser.
2. Click **Start Recording**, then **Stop**.
3. Your voice is sent to `/chat`.
4. Assistant transcribes → chats → replies with audio.
5. Audio reply auto-plays in the browser.

---

## 🔧 Troubleshooting

* **500 Internal Server Error**
  → Make sure your `.env` has the correct API key.
* **404 /v1/models**
  → This project does **not** proxy OpenAI’s REST API. Only call `/chat`.
* **Mic not working**
  → Ensure browser mic permissions are enabled.

---

## 📌 Requirements

* Python 3.10+
* Modern browser (Chrome/Edge/Firefox with MediaRecorder support)
* OpenAI API key with access to transcription, chat, and TTS models

---
