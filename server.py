from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from dotenv import load_dotenv
import os
import io
import json
import base64
import numpy as np
import soundfile as sf

# Load environment
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not set in .env file")

client = OpenAI(api_key=api_key)

# FastAPI app
app = FastAPI(title="Voice Assistant")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return PlainTextResponse("Place index.html in ./static/", status_code=404)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Voice Assistant"}


# ============================================================================
# WebSocket Voice Chat - Simplified Approach
# ============================================================================

@app.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket):
    """
    Real-time voice chat via WebSocket.
    Client sends: base64 encoded audio chunks
    Server sends: {"type": "transcript", "text": "..."} and {"type": "audio", "data": "base64..."}
    """
    await websocket.accept()
    print("[Voice WS] Client connected")
    
    # Audio buffer for accumulating chunks
    audio_buffer = []
    sample_rate = 16000  # We'll ask client to send 16kHz
    min_duration = 2.0  # Minimum 2 seconds before processing
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive()
            
            if data["type"] == "websocket.receive":
                if "text" in data:
                    msg = json.loads(data["text"])
                    
                    if msg["type"] == "audio_chunk":
                        # Client sends base64 encoded PCM16 audio
                        audio_b64 = msg["data"]
                        audio_bytes = base64.b64decode(audio_b64)
                        
                        # Convert bytes to int16 array
                        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
                        audio_buffer.extend(audio_int16)
                        
                    elif msg["type"] == "audio_end":
                        # Client finished speaking, process accumulated audio
                        if len(audio_buffer) > 0:
                            print(f"[Voice WS] Processing {len(audio_buffer)} samples ({len(audio_buffer)/sample_rate:.1f}s)")
                            
                            # Check minimum duration
                            duration = len(audio_buffer) / sample_rate
                            if duration < min_duration:
                                print(f"[Voice WS] Audio too short ({duration:.1f}s), skipping")
                                audio_buffer.clear()
                                await websocket.send_json({
                                    "type": "error",
                                    "message": f"Please speak for at least {min_duration} seconds"
                                })
                                continue
                            
                            # Convert to float32 and normalize
                            audio_float = np.array(audio_buffer, dtype=np.float32) / 32768.0
                            audio_buffer.clear()
                            
                            # Create WAV file in memory
                            wav_io = io.BytesIO()
                            sf.write(wav_io, audio_float, sample_rate, format='WAV', subtype='PCM_16')
                            wav_io.seek(0)
                            
                            # Transcribe with Whisper
                            try:
                                print("[Voice WS] Transcribing...")
                                transcript = client.audio.transcriptions.create(
                                    model="whisper-1",
                                    file=("audio.wav", wav_io, "audio/wav"),
                                    language="en",
                                    temperature=0.0
                                )
                                text = transcript.text.strip()
                                print(f"[Voice WS] Transcript: '{text}'")
                                
                                if not text:
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": "Could not understand audio"
                                    })
                                    continue
                                
                                # Send transcript to client
                                await websocket.send_json({
                                    "type": "transcript",
                                    "text": text
                                })
                                
                                # Generate response with GPT
                                print("[Voice WS] Generating response...")
                                chat_response = client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    messages=[
                                        {"role": "system", "content": "You are a helpful voice assistant. Keep responses concise and natural."},
                                        {"role": "user", "content": text}
                                    ]
                                )
                                reply_text = chat_response.choices[0].message.content
                                print(f"[Voice WS] Reply: '{reply_text}'")
                                
                                # Generate TTS
                                print("[Voice WS] Generating speech...")
                                tts_response = client.audio.speech.create(
                                    model="tts-1",
                                    voice="alloy",
                                    input=reply_text,
                                    response_format="mp3"
                                )
                                audio_data = tts_response.read()
                                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                                
                                # Send audio response
                                await websocket.send_json({
                                    "type": "audio",
                                    "data": audio_b64,
                                    "text": reply_text
                                })
                                print("[Voice WS] Response sent")
                                
                            except Exception as e:
                                print(f"[Voice WS] Error processing audio: {e}")
                                import traceback
                                traceback.print_exc()
                                await websocket.send_json({
                                    "type": "error",
                                    "message": f"Error: {str(e)}"
                                })
                    
                    elif msg["type"] == "clear":
                        # Client wants to clear buffer
                        audio_buffer.clear()
                        print("[Voice WS] Buffer cleared")
                        
    except WebSocketDisconnect:
        print("[Voice WS] Client disconnected")
    except Exception as e:
        print(f"[Voice WS] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[Voice WS] Connection closed")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)  