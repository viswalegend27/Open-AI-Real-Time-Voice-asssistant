from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from dotenv import load_dotenv
import os
import io

# ==== WebRTC related import ====
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect

import numpy as np
import soundfile as sf
import tempfile

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
# Uploaded audio file is Read
@app.post("/chat")
async def chat_voice(file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            # Backend reads the raw bytes
            raise HTTPException(status_code=400, detail="Empty file")

        # Transcription - Process
        filename = file.filename or "input.webm"
        audio_file = (filename, io.BytesIO(audio_bytes), file.content_type or "audio/webm")
        
        try:
            transcript = client.audio.transcriptions.create(
                # Model used for Transcription
                model="gpt-4o-transcribe",
                file=audio_file,
            )
        except Exception as e:
            print(f"gpt-4o-transcribe failed: {e}, falling back to whisper-1")
            # Reset BytesIO for retry
            audio_file = (filename, io.BytesIO(audio_bytes), file.content_type or "audio/webm")
            transcript = client.audio.transcriptions.create(
                # If failure occurs in our model then we are 
                model="whisper-1",
                file=audio_file,
            )

        text = transcript.text or ""
        # Transcribed text is displayed in our terminal
        print(f"Transcribed: {text}")

        # Chat
        chat = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful voice assistant."},
                {"role": "user", "content": text},
            ],
        )
        # Reply text is stored inside reply variable
        reply = chat.choices[0].message.content
        print(f"Reply: {reply}")

        # TTS streaming (MP3)
        def tts_stream():
            with client.audio.speech.with_streaming_response.create(
                model="tts-1",  # openAI's tts model
                voice="alloy",
                input=reply,
                response_format="mp3", # Synthesize the reply into MP3
            ) as resp:
                for chunk in resp.iter_bytes():
                    yield chunk

        return StreamingResponse(tts_stream(), media_type="audio/mpeg")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat_voice: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")


# ==== NEW: WebRTC signaling and audio receiver ====
class AudioReceiver(MediaStreamTrack): # Class to handle our WebRTC audio
    kind = "audio"
    def __init__(self, track, on_complete):
        super().__init__()
        self.track = track
        self.buffers = []  # Stores numpy arrays of raw audio data
        self.on_complete = on_complete
        self.closed = False

    async def recv(self):
        frame = await self.track.recv()
        # aiortc frame is 16-bit PCM, samples per channel
        pcm = frame.to_ndarray()
        self.buffers.append(pcm.copy()) # add every frame to the buffer
        print(f"[WebRTC] Received frame ({pcm.shape})")
        return frame

    async def stop_and_process(self, sample_rate=48000):
        if self.closed or not self.buffers:
            return
        self.closed = True
        # Merge all frames into one array
        audio_data = np.concatenate(self.buffers, axis=1) if len(self.buffers) else None
        # Mono or stereo: always write as 16-bit little-endian WAV for OpenAI
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            sf.write(tmp.name, audio_data.T, sample_rate, subtype='PCM_16')
            tmp.flush()
            tmp.seek(0)
            # Prepare file for OpenAI (simulate UploadFile)
            audio_file = ("input.wav", tmp, "audio/wav")
            print("[WebRTC] Sending buffered audio to OpenAI...")
            try:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
                text = transcript.text or ""
                print(f"[WebRTC] Transcribed: {text}")
                await self.on_complete(text)
            except Exception as e:
                print(f"[WebRTC] Transcription error: {e}")


@app.websocket("/ws") # Web RTC used is Fast API's route /ws 
                      # Uses aiortc's for handling connections and recieving data
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pc = RTCPeerConnection()  # Our new aiortc connection
    audio_receiver = None
    # Function used for audio transcription
    async def handle_complete(text):
        # Respond with the transcribed text and also with audio reply
        try:
            await websocket.send_text(json.dumps({"transcript": text}))
            # Get a chat reply
            chat = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful voice assistant."},
                    {"role": "user", "content": text},
                ],
            )
            reply = chat.choices[0].message.content
            print(f"[WebRTC] Reply: {reply}")

            # TTS (MP3) in memory
            buf = bytearray()
            with client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice="alloy",
                input=reply,
                response_format="mp3",
            ) as resp:
                for chunk in resp.iter_bytes():
                    buf.extend(chunk)
            # Send the MP3 audio as binary over WebSocket
            await websocket.send_bytes(bytes(buf))
        except Exception as e:
            print(f"[WebRTC] Chat or TTS error: {e}")

    try:
        # Connecting incoming audio track 
        @pc.on("track")
        def on_track(track):
            nonlocal audio_receiver
            if track.kind == "audio":
                audio_receiver = AudioReceiver(track, handle_complete)
                print("[WebRTC] Remote audio track received and buffering.")
                
                # Listen for the track ending and process audio immediately
                @track.on("ended")
                async def on_ended():
                    print("[WebRTC] Audio track ended. Processing audio...")
                    if audio_receiver:
                        await audio_receiver.stop_and_process()

        # Needs debugging and further processing
        while True:
            # Support both text and bytes (ignore bytes unless they're browser pings)
            data = await websocket.receive()
            msg = None
            if data.get("type") == "websocket.receive":
                raw = data.get("text")
                if raw:
                    msg = json.loads(raw)
            if not msg:
                continue
            if msg["type"] == "offer":
                offer = RTCSessionDescription(sdp=msg["sdp"], type=msg["type"])
                await pc.setRemoteDescription(offer)
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)
                await websocket.send_text(json.dumps({
                    "type": pc.localDescription.type,
                    "sdp": pc.localDescription.sdp,
                }))
            elif msg["type"] == "candidate":
                candidate = msg["candidate"]
                await pc.addIceCandidate(candidate)
    except WebSocketDisconnect:
        if audio_receiver:
            await audio_receiver.stop_and_process()
        await pc.close()