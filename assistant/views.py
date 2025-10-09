"""Views for Mahindra Voice Assistant API endpoints"""

from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
import os
import httpx
import logging
from pathlib import Path
from dotenv import load_dotenv
import constants as C

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
    payload = C.get_session_payload() # session payload recieved
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


@csrf_exempt
def save_conversation(request):
    """Save conversation message"""
    import json
    from assistant.analyzer import save_message
    
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        role = data.get('role')
        content = data.get('content')
        
        if not all([session_id, role, content]):
            return JsonResponse({"error": "Missing required fields"}, status=400)
        
        result = save_message(session_id, role, content)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def get_analysis(request):
    """Get conversation analysis"""
    from assistant.analyzer import analyze_conversation
    
    session_id = request.GET.get('session_id')
    if not session_id:
        return JsonResponse({"error": "session_id required"}, status=400)
    
    result = analyze_conversation(session_id)
    return JsonResponse(result)


@csrf_exempt
def get_recommendations(request):
    """Get vehicle recommendations"""
    from assistant.analyzer import get_recommendations as get_recs
    
    session_id = request.GET.get('session_id')
    if not session_id:
        return JsonResponse({"error": "session_id required"}, status=400)
    
    result = get_recs(session_id)
    return JsonResponse(result)
