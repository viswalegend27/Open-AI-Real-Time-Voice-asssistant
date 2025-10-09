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

@csrf_exempt
def generate_summary(request):
    """Generate AI-powered conversation summary"""
    from assistant.analyzer import generate_conversation_summary
    import json
    
    # Get session_id from GET, POST params, or request body
    session_id = request.GET.get('session_id') or request.POST.get('session_id')
    
    if not session_id and request.body:
        try:
            body_data = json.loads(request.body)
            session_id = body_data.get('session_id')
        except:
            pass
    
    if not session_id:
        return JsonResponse({"error": "session_id required"}, status=400)
    
    result = generate_conversation_summary(session_id)
    
    # If successful, include the formatted summary for easy display
    if result.get('status') == 'success' and result.get('formatted_summary'):
        result['display_text'] = result['formatted_summary']
    
    return JsonResponse(result)

@csrf_exempt
def get_summary(request, session_id):
    """Retrieve existing conversation summary"""
    from assistant.models import Conversation
    
    try:
        conv = Conversation.objects.get(session_id=session_id)
        
        # Check if summary exists
        if hasattr(conv, 'summary'):
            summary = conv.summary
            return JsonResponse({
                "status": "success",
                "summary": {
                    "text": summary.summary_text,
                    "customer_name": summary.customer_name,
                    "contact_info": summary.contact_info,
                    "budget_range": summary.budget_range,
                    "vehicle_type": summary.vehicle_type,
                    "use_case": summary.use_case,
                    "priority_features": summary.priority_features,
                    "recommended_vehicles": summary.recommended_vehicles,
                    "next_actions": summary.next_actions,
                    "sentiment": summary.sentiment,
                    "engagement_score": summary.engagement_score,
                    "purchase_intent": summary.purchase_intent,
                    "generated_at": summary.generated_at.isoformat()
                },
                "conversation": {
                    "session_id": conv.session_id,
                    "started_at": conv.started_at.isoformat(),
                    "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
                    "total_messages": conv.total_messages
                }
            })
        else:
            return JsonResponse({
                "status": "not_found",
                "message": "Summary not generated yet. Call /api/generate-summary/ first."
            }, status=404)
            
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found"}, status=404)
