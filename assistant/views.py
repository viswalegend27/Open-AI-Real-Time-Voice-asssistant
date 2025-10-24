from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from pathlib import Path
import os
import json
import httpx
import logging
from dotenv import load_dotenv
import constants as C
from assistant.analyzer import save_message, analyze_conversation, generate_conversation_summary, generate_summary_task
from assistant.models import Conversation

load_dotenv()
logger = logging.getLogger(__name__)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in .env file")

OPENAI_MODEL = os.getenv("OPENAI_REALTIME_MODEL", C.DEFAULT_REALTIME_MODEL)
OPENAI_VOICE = os.getenv("OPENAI_REALTIME_VOICE", C.DEFAULT_VOICE)
OPENAI_TRANSCRIBE = os.getenv("TRANSCRIBE_MODEL", C.DEFAULT_TRANSCRIBE_MODEL)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

def _json_error(message, status=400):
    return JsonResponse({"error": message}, status=status)

def _parse_body(request):
    if hasattr(request, "body") and request.body:
        try:
            return json.loads(request.body)
        except Exception:
            pass
    return {}

def _get_session_id(request):
    session_id = request.GET.get('session_id') or request.POST.get('session_id')
    if not session_id:
        data = _parse_body(request)
        session_id = data.get('session_id')
    return session_id

def read_root(request):
    html_file = STATIC_DIR / "index_new.html"
    if html_file.exists():
        return FileResponse(open(html_file, 'rb'))
    return _json_error("HTML not found", 404)

@csrf_exempt
def create_realtime_session(request):
    payload = C.get_session_payload()
    payload.update({"model": OPENAI_MODEL, "voice": OPENAI_VOICE, "input_audio_transcription": {"model": OPENAI_TRANSCRIBE}})
    logger.info(f"Creating session | model={OPENAI_MODEL} | voice={OPENAI_VOICE}")
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
            "OpenAI-Beta": C.OPENAI_BETA_HEADER_VALUE
        }
        with httpx.Client(timeout=20.0) as client:
            response = client.post(C.get_realtime_session_url(), headers=headers, json=payload)
            if response.status_code != 200:
                logger.error(f"OpenAI error ({response.status_code}): {response.text}")
                return _json_error(f"Session error: {response.text}", response.status_code)
            data = response.json()
            logger.info(f"Session created | id={data.get('id')}")
            return JsonResponse(data)
    except Exception as e:
        logger.error(f"Session creation failed: {e}", exc_info=True)
        return _json_error(str(e), 500)

@csrf_exempt
def save_conversation(request):
    try:
        data = _parse_body(request)
        session_id, role, content = data.get('session_id'), data.get('role'), data.get('content')
        if not (session_id and role and content):
            return _json_error("Missing required fields", 400)
        result = save_message(session_id, role, content)
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"save_conversation error: {e}", exc_info=True)
        return _json_error(str(e), 500)

@csrf_exempt
def get_analysis(request):
    session_id = _get_session_id(request)
    if not session_id:
        return _json_error("session_id required", 400)
    result = analyze_conversation(session_id)
    return JsonResponse(result)

@csrf_exempt
def generate_summary(request):
    session_id = _get_session_id(request)
    if not session_id:
        return _json_error("session_id required", 400)
    task = generate_summary_task.delay(session_id)
    return JsonResponse({'status': 'processing', 'task_id': task.id, 'message': 'Summary generation started.'})

@csrf_exempt
def get_summary(request, session_id):
    try:
        conv = Conversation.objects.get(session_id=session_id)
        summary = conv.summary_data or {}
        if summary:
            return JsonResponse({
                "status": "success",
                "summary": {
                    "text": summary.get("summary"),
                    "customer_name": summary.data.get("customer_name"),
                    "contact_info": summary.data.get("contact_info"),
                    "budget_range": summary.data.get("budget_range"),
                    "vehicle_type": summary.data.get("vehicle_type"),
                    "use_case": summary.data.get("use_case"),
                    "priority_features": summary.data.get("priority_features", []),
                    "recommended_vehicles": summary.data.get("recommended_vehicles", []),
                    "next_actions": summary.data.get("next_actions", []),
                    "sentiment": summary.data.get("sentiment"),
                    "engagement_score": summary.data.get("engagement_score"),
                    "purchase_intent": summary.data.get("purchase_intent"),
                    "generated_at": conv.summary_generated_at.isoformat() if conv.summary_generated_at else None
                },
                "conversation": {
                    "session_id": conv.session_id,
                    "started_at": conv.started_at.isoformat(),
                    "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
                    "total_messages": conv.total_messages
                }
            })
        return JsonResponse({
            "status": "not_found",
            "message": "Summary not generated yet. Call /api/generate-summary/ first."
        }, status=404)
    except Conversation.DoesNotExist:
        logger.error(f"Conversation not found: {session_id}")
        return _json_error("Conversation not found", 404)
    except Exception as e:
        logger.error(f"get_summary error: {e}", exc_info=True)
        return _json_error(str(e), 500)

@csrf_exempt
def list_vehicle_interests(request):
    from assistant.models import VehicleInterest
    interests = VehicleInterest.objects.select_related('conversation').all().order_by('-timestamp')
    data = [{
        "id": vi.id,
        "vehicle_name": vi.vehicle_name,
        "interest_level": vi.meta.get("interest_level"),
        "mentioned_features": vi.meta.get("mentioned_features", []),
        "timestamp": vi.timestamp.isoformat(),
        "conversation_id": vi.conversation.session_id,
        "user_id": vi.conversation.user_id,
    } for vi in interests]
    return JsonResponse({"vehicle_interests": data})
