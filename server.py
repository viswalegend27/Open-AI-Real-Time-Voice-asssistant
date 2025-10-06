from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from dotenv import load_dotenv
import os
import io

# ==== Env & OpenAI ====
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not set in env or .env")

client = OpenAI(api_key=api_key)

# ==== FastAPI app must be created BEFORE any @app.* decorators ====
app = FastAPI()

# ==== CORS ====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==== Optional log helper for stray /v1/* calls (debug only) ====
@app.middleware("http")
async def debug_v1_calls(request: Request, call_next):
    if request.url.path.startswith("/v1/"):
        ua = request.headers.get("user-agent", "")
        ref = request.headers.get("referer", "")
        print(f"[WARN] /v1/* hit from {request.client.host} UA='{ua}' Referer='{ref}' Path='{request.url.path}'")
    return await call_next(request)

# ==== Static ====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return PlainTextResponse("Place index.html in ./static/index.html", status_code=200)

# ==== Voice Chat ====
@app.post("/chat")
async def chat_voice(file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        # Transcription - pass file as tuple (filename, file_object, content_type)
        filename = file.filename or "input.webm"
        audio_file = (filename, io.BytesIO(audio_bytes), file.content_type or "audio/webm")
        
        try:
            transcript = client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=audio_file,
            )
        except Exception as e:
            print(f"gpt-4o-transcribe failed: {e}, falling back to whisper-1")
            # Reset BytesIO for retry
            audio_file = (filename, io.BytesIO(audio_bytes), file.content_type or "audio/webm")
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )

        text = transcript.text or ""
        print(f"Transcribed: {text}")

        # Chat
        chat = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful voice assistant."},
                {"role": "user", "content": text},
            ],
        )
        reply = chat.choices[0].message.content
        print(f"Reply: {reply}")

        # TTS streaming (MP3)
        def tts_stream():
            with client.audio.speech.with_streaming_response.create(
                model="tts-1",  # or tts-1-hd
                voice="alloy",
                input=reply,
                response_format="mp3",
            ) as resp:
                for chunk in resp.iter_bytes():
                    yield chunk

        return StreamingResponse(tts_stream(), media_type="audio/mpeg")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat_voice: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")