from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
import os, httpx, logging
import constants as C
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in .env file")

OPENAI_MODEL = os.getenv("OPENAI_REALTIME_MODEL", C.DEFAULT_REALTIME_MODEL)
OPENAI_VOICE = os.getenv("OPENAI_REALTIME_VOICE", C.DEFAULT_VOICE)
OPENAI_TRANSCRIBE = os.getenv("TRANSCRIBE_MODEL", C.DEFAULT_TRANSCRIBE_MODEL)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def read_root(request):
    """Serve main interface"""
    html_file = STATIC_DIR / "index_new.html"
    return FileResponse(open(html_file, 'rb')) if html_file.exists() else JsonResponse({"error": "HTML not found"}, status=404)


@csrf_exempt
def create_realtime_session(request):
    """Create OpenAI session"""
    payload = C.get_session_payload()
    payload.update({"model": OPENAI_MODEL, "voice": OPENAI_VOICE, "input_audio_transcription": {"model": OPENAI_TRANSCRIBE}})
    
    logger.info(f"Creating session | model={OPENAI_MODEL} | voice={OPENAI_VOICE}")
    
    try:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json", "OpenAI-Beta": C.OPENAI_BETA_HEADER_VALUE}
        with httpx.Client(timeout=20.0) as client:
            response = client.post(C.get_realtime_session_url(), headers=headers, json=payload)
        
        if response.status_code != 200:
            logger.error(f"OpenAI error ({response.status_code}): {response.text}")
            return JsonResponse({"detail": f"Session error: {response.text}"}, status=response.status_code)
        
        data = response.json()
        logger.info(f"Session created | id={data.get('id')}")
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Session creation failed: {e}", exc_info=True)
        return JsonResponse({"detail": str(e)}, status=500)


def health_check(request):
    """Health check"""
    return JsonResponse({"status": "ok", "agent": C.AI_AGENT_NAME, "model": OPENAI_MODEL, "voice": OPENAI_VOICE})