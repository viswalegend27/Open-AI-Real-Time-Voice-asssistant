from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from dotenv import load_dotenv
import os
import io

# ==== WebRTC related import ====
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCIceCandidate
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
    # Data is received via get method
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return PlainTextResponse("Place index.html in ./static/index.html", status_code=200)

# ==== Voice Chat ====
# Uploaded audio file is Read
@app.post("/chat")
# Process the recorded file from the frontend
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
                response_format="mp3",  # Synthesize the reply into MP3
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
class AudioReceiver(MediaStreamTrack):  # Class to handle our WebRTC audio
    kind = "audio"

    def __init__(self, track, on_complete, min_seconds=3):
        super().__init__()
        self.track = track
        self.buffers = []  # Stores numpy arrays of raw audio data
        self.on_complete = on_complete
        self.closed = False
        self.sample_rate = 48000
        self.min_seconds = min_seconds  # flush after N seconds
        self.frames_per_buffer = int(self.sample_rate * self.min_seconds / 960)  # estimated for 960-sample (20ms) frames
        self.frame_count = 0
        self.process_task = None
        self.sending = False

    async def recv(self):
        try:
            frame = await self.track.recv()
            pcm = frame.to_ndarray()
            self.buffers.append(pcm.copy())
            self.frame_count += 1
            print(f"[WebRTC] Received frame ({pcm.shape}), total: {self.frame_count}")
            if not self.sending and len(self.buffers) >= self.frames_per_buffer:
                self.sending = True
                asyncio.create_task(self.flush_and_process())
            return frame
        except Exception as e:
            print(f"[WebRTC] recv error: {e}")
            return None

    async def flush_and_process(self):
        # Defensive: only process if buffer is big enough and not empty
        if not self.buffers:
            self.sending = False
            return
        audio_buffers = self.buffers.copy()
        self.buffers.clear()
        self.frame_count = 0
        print(f"[WebRTC] Flushing {len(audio_buffers)} frames to OpenAI...")
        audio_data = np.concatenate(audio_buffers, axis=1) if len(audio_buffers) else None
        
        # Convert to mono if stereo
        if audio_data is not None and audio_data.shape[0] > 1:
            audio_data = np.mean(audio_data, axis=0, keepdims=True)
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            sf.write(tmp.name, audio_data.T, self.sample_rate, subtype='PCM_16')
            tmp.flush()
            tmp.seek(0)
            audio_file = ("input.wav", tmp, "audio/wav")
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
                self.sending = False

    async def stop_and_process(self, sample_rate=48000):
        self.sample_rate = sample_rate
        if self.closed:
            return
        self.closed = True
        await self.flush_and_process()

# Web-socket endpoint created here
@app.websocket("/ws")  # Web RTC used is Fast API's route /ws
# Uses aiortc's for handling connections and receiving data
async def websocket_endpoint(websocket: WebSocket):
    # Accepts the connection
    await websocket.accept()
    # Webrtc peerConnection created
    pc = RTCPeerConnection()  # Our new aiortc connection
    audio_receiver = None
    
    # Function used for audio transcription
    async def handle_complete(text):
        # Respond with the transcribed text and also with audio reply
        try:
            # Audio is send to the websocket
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
        # Peerconnection used for listening the audio 
        def on_track(track):
            nonlocal audio_receiver
            if track.kind == "audio":
                # Once the audio recieved completes it is stored in audio_reciever
                audio_receiver = AudioReceiver(track, handle_complete, min_seconds=3)
                print("[WebRTC] Remote audio track received and buffering.")
                
                # Use add_listener instead of decorator to avoid scoping issues
                async def on_ended():
                    print("[WebRTC] Audio track ended. Processing audio...")
                    if audio_receiver:
                        await audio_receiver.stop_and_process()
                
                track.add_listener("ended", on_ended)

        # WebRTC signaling
        while True:
            try:
                data = await websocket.receive()
                if data["type"] == "websocket.receive" and "text" in data:
                    msg = json.loads(data["text"])
                    
                    if msg["type"] == "offer":
                        # Server handles the webRTC signaling 
                        offer = RTCSessionDescription(sdp=msg["sdp"], type=msg["type"])
                        await pc.setRemoteDescription(offer)
                        answer = await pc.createAnswer()
                        await pc.setLocalDescription(answer)
                        await websocket.send_text(json.dumps({
                            "type": pc.localDescription.type,
                            "sdp": pc.localDescription.sdp,
                        }))
                    elif msg["type"] == "candidate":
                        candict = msg["candidate"]
                        if candict and candict.get('candidate'):
                            # Properly handle candidate parameters
                            candidate = RTCIceCandidate(
                                candict['candidate'],
                                sdpMid=candict.get('sdpMid', ''),
                                sdpMLineIndex=candict.get('sdpMLineIndex', -1)
                            )
                            await pc.addIceCandidate(candidate)
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                print("Received non-JSON message")
            except Exception as e:
                print(f"WebSocket error: {e}")
                break

    finally:
        # Cleanup resources
        print("Cleaning up WebRTC resources")
        if audio_receiver:
            await audio_receiver.stop_and_process()
        if pc:
            await pc.close()