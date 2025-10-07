"""
Ishmael - OpenAI Realtime Voice Assistant Server
Creates ephemeral sessions for browser-to-OpenAI WebRTC connections
"Call me Ishmael..." - Your intelligent technical companion
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os
import httpx
import logging
import constants as C

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", C.DEFAULT_REALTIME_MODEL)
OPENAI_VOICE = os.getenv("OPENAI_REALTIME_VOICE", C.DEFAULT_VOICE)
OPENAI_TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", C.DEFAULT_TRANSCRIBE_MODEL)

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in .env file")

# FastAPI app
app = FastAPI(title=f"{C.AI_AGENT_NAME} - Realtime Voice Assistant")

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
async def read_root():
    """Serve the main Ishmael interface"""
    # Try new Ishmael interface first
    ishmael_page = os.path.join(STATIC_DIR, "index_new.html")
    if os.path.exists(ishmael_page):
        return FileResponse(ishmael_page)
    
    # Fallback to old interface
    realtime_page = os.path.join(STATIC_DIR, "realtime.html")
    if os.path.exists(realtime_page):
        return FileResponse(realtime_page)
    
    return JSONResponse(
        {"error": "Interface HTML not found in static folder"},
        status_code=404
    )


@app.get("/session/")
@app.post("/session/")
@app.get("/api/session")
@app.post("/api/session")
async def create_realtime_session():
    """
    Creates an ephemeral OpenAI Realtime session for browser WebRTC.
    Returns a client_secret that the browser uses to connect directly to OpenAI.
    """
    
    # Get payload from constants
    payload = C.get_session_payload()
    # Override with environment variables if set
    payload["model"] = OPENAI_REALTIME_MODEL
    payload["voice"] = OPENAI_VOICE
    payload["input_audio_transcription"]["model"] = OPENAI_TRANSCRIBE_MODEL
    
    logger.info(
        f"Creating Realtime session | model={OPENAI_REALTIME_MODEL} | "
        f"voice={OPENAI_VOICE} | transcribe={OPENAI_TRANSCRIBE_MODEL}"
    )
    
    try:
        # Make request to OpenAI Realtime API
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
            "OpenAI-Beta": C.OPENAI_BETA_HEADER_VALUE,
        }
        
        url = C.get_realtime_session_url()
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"OpenAI session error ({response.status_code}): {error_text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"OpenAI session error: {error_text}"
            )
        
        data = response.json()
        
        logger.info(
            f"Realtime session created | id={data.get('id')} | "
            f"expires_at={data.get('expires_at')}"
        )
        
        return JSONResponse(data)
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error creating session: {e}")
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": f"{C.AI_AGENT_NAME} - Realtime Voice Assistant",
        "agent_name": C.AI_AGENT_NAME,
        "agent_role": C.AI_AGENT_ROLE,
        "model": OPENAI_REALTIME_MODEL,
        "voice": OPENAI_VOICE
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("=" * 70)
    logger.info(f"🧭 Starting {C.AI_AGENT_NAME} - Realtime Voice Assistant Server")
    logger.info("   'Call me Ishmael...'")
    logger.info("=" * 70)
    logger.info(f"AI Agent: {C.AI_AGENT_NAME}")
    logger.info(f"Role: {C.AI_AGENT_ROLE}")
    logger.info(f"Model: {OPENAI_REALTIME_MODEL}")
    logger.info(f"Voice: {OPENAI_VOICE}")
    logger.info(f"Transcription: {OPENAI_TRANSCRIBE_MODEL}")
    logger.info("=" * 70)
    logger.info("⛵ Open http://127.0.0.1:8000 in your browser")
    logger.info("   Begin your journey with Ishmael!")
    logger.info("=" * 70)
    uvicorn.run(app, host="127.0.0.1", port=8000)
