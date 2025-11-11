from pathlib import Path
import os
import json
import logging
from typing import Any, Dict, Optional
import httpx
from dotenv import load_dotenv
from django.http import JsonResponse, FileResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
import constants as C
from assistant.analyzer import save_message, analyze_conversation, generate_summary_task
from assistant.models import Conversation
from assistant.serializers import (
    VehicleInterestSerializer,
    ConversationShortSerializer,
    SummarySerializer,
)
load_dotenv()
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in .env file")

OPENAI_MODEL = os.getenv("OPENAI_REALTIME_MODEL", C.DEFAULT_REALTIME_MODEL)
OPENAI_VOICE = os.getenv("OPENAI_REALTIME_VOICE", C.DEFAULT_VOICE)
OPENAI_TRANSCRIBE = os.getenv("TRANSCRIBE_MODEL", C.DEFAULT_TRANSCRIBE_MODEL)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

def _json_response(payload: Dict[str, Any], status: int = 200) -> JsonResponse:
    return JsonResponse(payload, status=status, safe=False)

def _json_error(message: str, status: int = 400) -> JsonResponse:
    return _json_response({"error": message}, status=status)

def _parse_body(request: HttpRequest) -> Dict[str, Any]:
    try:
        if getattr(request, "body", None):
            return json.loads(request.body)
    except Exception:
        logger.debug("Failed to parse JSON body", exc_info=True)
    return {}

def _get_session_id(request: HttpRequest) -> Optional[str]:
    # Prefer query/post params, fall back to JSON body
    session_id = request.GET.get("session_id") or request.POST.get("session_id")
    if session_id:
        return session_id
    data = _parse_body(request)
    return data.get("session_id")

def _openai_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": C.OPENAI_BETA_HEADER_VALUE,
    }

def read_root(request: HttpRequest) -> JsonResponse | FileResponse:
    html_file = STATIC_DIR / "index_new.html"
    if html_file.exists():
        return FileResponse(open(html_file, "rb"))
    return _json_error("HTML not found", 404)

@csrf_exempt
def create_realtime_session(request: HttpRequest) -> JsonResponse:
    payload = C.get_session_payload()
    payload.update({
        "model": OPENAI_MODEL,
        "voice": OPENAI_VOICE,
        "input_audio_transcription": {"model": OPENAI_TRANSCRIBE},
    })
    logger.info("Creating realtime session", extra={"model": OPENAI_MODEL, "voice": OPENAI_VOICE})

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(C.get_realtime_session_url(), headers=_openai_headers(), json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info("Session created", extra={"session_id": data.get("id")})
            return _json_response(data)
    except httpx.HTTPStatusError as e:
        logger.error("OpenAI returned non-200 response", exc_info=True)
        return _json_error(f"Session error: {e.response.text}", status=e.response.status_code)
    except Exception as e:
        logger.exception("Session creation failed")
        return _json_error(str(e), 500)

@csrf_exempt
def save_conversation(request: HttpRequest) -> JsonResponse:
    data = _parse_body(request)
    session_id = data.get("session_id")
    role = data.get("role")
    content = data.get("content")

    if not (session_id and role and content):
        return _json_error("Missing required fields: session_id, role, content", 400)

    try:
        result = save_message(session_id, role, content)
        return _json_response(result)
    except Exception as e:
        logger.exception("save_conversation error")
        return _json_error(str(e), 500)

# -- Saving message as a batch. 
@csrf_exempt
def save_conversation_batch(request: HttpRequest) -> JsonResponse:
    data = _parse_body(request)
    messages = data.get("messages", [])
    
    if not messages or not isinstance(messages, list):
        return _json_error("Missing or invalid 'messages' array", 400)
    
    try:
        from assistant.analyzer import save_message_batch
        result = save_message_batch(messages)
        return _json_response(result)
    except Exception as e:
        logger.exception("save_conversation_batch error")
        return _json_error(str(e), 500)

@csrf_exempt
def get_analysis(request: HttpRequest) -> JsonResponse:
    session_id = _get_session_id(request)
    if not session_id:
        return _json_error("session_id required", 400)

    try:
        result = analyze_conversation(session_id)
        return _json_response(result)
    except Exception as e:
        logger.exception("get_analysis error")
        return _json_error(str(e), 500)

@csrf_exempt
def generate_summary(request: HttpRequest) -> JsonResponse:
    session_id = _get_session_id(request)
    if not session_id:
        return _json_error("session_id required", 400)

    try:
        task = generate_summary_task.delay(session_id)
        return _json_response({"status": "processing", "task_id": task.id, "message": "Summary generation started."})
    except Exception as e:
        logger.exception("generate_summary error")
        return _json_error(str(e), 500)

@csrf_exempt
def get_summary(request: HttpRequest, session_id: str) -> JsonResponse:
    try:
        conv = Conversation.objects.get(session_id=session_id)
        summary = conv.summary_data or {}
        if not summary:
            return _json_response({"status": "not_found", "message": "Summary not generated yet. Call /api/generate-summary/ first."}, status=404)

        # enrich summary with generated timestamp
        summary_data = {**summary, "generated_at": conv.summary_generated_at}
        summary_serialized = SummarySerializer(summary_data).data
        conversation_serialized = ConversationShortSerializer(conv).data
        return _json_response({"status": "success", "summary": summary_serialized, "conversation": conversation_serialized})
    except Conversation.DoesNotExist:
        logger.warning("Conversation not found: %s", session_id)
        return _json_error("Conversation not found", 404)
    except Exception as e:
        logger.exception("get_summary error")
        return _json_error(str(e), 500)

@csrf_exempt
def list_vehicle_interests(request: HttpRequest) -> JsonResponse:
    from assistant.models import VehicleInterest  # local import keeps module import light

    try:
        interests = VehicleInterest.objects.select_related("conversation").all().order_by("-timestamp")
        serializer = VehicleInterestSerializer(interests, many=True)
        return _json_response({"vehicle_interests": serializer.data})
    except Exception as e:
        logger.exception("list_vehicle_interests error")
        return _json_error(str(e), 500)
