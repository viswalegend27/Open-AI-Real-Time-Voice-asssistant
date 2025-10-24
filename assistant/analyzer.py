import os, json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from django.utils import timezone
from django.db import transaction
from assistant.models import Conversation, UserPreference, VehicleInterest, ConversationSummary
from celery import shared_task

load_dotenv()

try:
    from openai import OpenAI
    OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    OPENAI_CLIENT = None


def openai_chat(prompt: str, user_content: Optional[str] = None,
    model: str = "gpt-4o-mini", temp: float = 0.2) -> Optional[Any]:
    if not OPENAI_CLIENT:
        return None
    try:
        msgs = [{"role": "system", "content": prompt}]
        if user_content:
            msgs.append({"role": "user", "content": user_content})
        resp = OPENAI_CLIENT.chat.completions.create(
            model=model, messages=msgs, temperature=temp,
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return None

def get_mahindra_vehicles() -> Dict[str, Dict[str, Any]]:
    # use function schema
    prompt = (
        "You are an expert on Mahindra vehicles. List major Mahindra passenger vehicles currently on sale in India "
        "and return a JSON mapping: { 'ModelName': { 'type': 'SUV/EV/etc', 'segment': 'premium/compact/etc', 'features': [...] } }."
        "Return only real, current models."
    )
    fetched = openai_chat(prompt, temp=0.1)
    return fetched if isinstance(fetched, dict) and fetched else _FALLBACK_MAHINDRA

def _user_texts(conv: Conversation) -> List[str]:
    return [m.get("content") for m in (conv.messages_json or []) if m.get("role") == "user" and m.get("content")]

@shared_task
# Here we register the generate_summary_task as a Celery task
def generate_summary_task(session_id):
    return generate_conversation_summary(session_id)

def analyze_conversation(session_id: str) -> Dict[str, Any]:
    try:
        conv = Conversation.objects.get(session_id=session_id)
    except Conversation.DoesNotExist:
        return {"status": "error", "message": "conversation not found"}

    texts = _user_texts(conv)
    if not texts:
        return {"status": "no_action", "message": "no user messages"}

    all_text = "\n".join(f"Customer: {t}" for t in texts)
    prompt = (
        "You are an expert car sales assistant. From the conversation text, extract and return JSON with keys: "
        '{"budget":"number+unit or null","usage":"family/adventure/city/commercial or null",'
        '"priority_features":["..."],"vehicle_interest":["Model names"] ,"other_insights":null } '
        "Only extract what is explicitly said or clearly implied."
    )
    extracted = openai_chat(prompt, all_text) or {}
    if not isinstance(extracted, dict):
        extracted = {}

    try:
        with transaction.atomic():
            # Save simple prefs
            for key in ("budget", "usage"):
                val = extracted.get(key)
                if val:
                    UserPreference.objects.update_or_create(
                        conversation=conv, data__type=key,
                        defaults={"data": {"type": key, "value": str(val), "confidence": 0.8}, "extracted_at": timezone.now()}
                    )

            # Priority features
            pf = extracted.get("priority_features")
            if pf:
                UserPreference.objects.update_or_create(
                    conversation=conv, data__type="priority_features",
                    defaults={"data": {"type": "priority_features", "value": json.dumps(pf), "confidence": 0.7},
                              "extracted_at": timezone.now()}
                )

            # Vehicle interests (add new or update existing)
            vehicles = [v for v in (extracted.get("vehicle_interest") or []) if v]
            if vehicles:
                existing = set(VehicleInterest.objects.filter(conversation=conv, vehicle_name__in=vehicles)
                               .values_list("vehicle_name", flat=True))
                now = timezone.now()
                to_create = [VehicleInterest(conversation=conv, vehicle_name=v, meta={"interest_level": 8}, timestamp=now)
                             for v in vehicles if v not in existing]
                if to_create:
                    VehicleInterest.objects.bulk_create(to_create)
                # update existing interest meta/timestamp
                VehicleInterest.objects.filter(conversation=conv, vehicle_name__in=vehicles).update(meta={"interest_level": 8}, timestamp=now)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {"status": "success", "extracted": extracted}

def save_message(session_id: str, role: str, content: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    conv, _ = Conversation.objects.get_or_create(session_id=session_id, defaults={"user_id": user_id})
    msgs = list(conv.messages_json or [])
    msgs.append({"role": role, "content": content, "timestamp": timezone.now().isoformat()})
    conv.messages_json = msgs
    conv.total_messages = len(msgs)
    conv.save(update_fields=["messages_json", "total_messages"])
    analysis = analyze_conversation(session_id)
    return {"status": "success", "message_count": conv.total_messages, "analysis": analysis}

def generate_conversation_summary(session_id: str) -> Dict[str, Any]:
    try:
        conv = Conversation.objects.get(session_id=session_id)
    except Conversation.DoesNotExist:
        return {"status": "error", "message": "conversation not found"}

    msgs = conv.messages_json or []
    if not msgs:
        return {"status": "error", "message": "No messages"}

    transcript = "\n".join(f"{'Customer' if m['role']=='user' else 'Ishmael'}: {m['content']}" for m in msgs)
    prompt = (
        f"You are analyzing a completed sales conversation. CONVERSATION: {transcript}\n\n"
        "Return JSON with: summary(2 sentences), customer_name|null, contact_info|null, budget_range|null, "
        'vehicle_type|null, use_case|null, priority_features[], recommended_vehicles[], next_actions[], '
        "sentiment, engagement_score(1-10), purchase_intent(high/medium/low). Use null when unknown. Make it concise." 
    )

    summary_data = openai_chat(prompt, temp=0.3) or {}
    if not isinstance(summary_data, dict) or not summary_data:
        # fallback
        interests = [i.vehicle_name for i in conv.vehicle_interests.all()]
        summary_data = {
            "summary": f"Conversation with {len(msgs)} messages; customer showed interest in vehicles.",
            "customer_name": None, "contact_info": None, "budget_range": None,
            "vehicle_type": "SUV" if interests else None, "use_case": None,
            "priority_features": [], "recommended_vehicles": interests,
            "next_actions": ["Follow up", "Offer test drive"], "sentiment": "neutral",
            "engagement_score": 5, "purchase_intent": "medium"
        }

    for pref in conv.preferences.all():
        if pref.data.get("type") == "budget" and not summary_data.get("budget_range"):
            summary_data["budget_range"] = pref.data.get("value")
        if pref.data.get("type") == "usage" and not summary_data.get("use_case"):
            summary_data["use_case"] = pref.data.get("value")

    summary_obj, _ = ConversationSummary.objects.update_or_create(
        conversation=conv, defaults={"data": summary_data, "generated_at": timezone.now()}
    )

    if not conv.ended_at:
        conv.ended_at = timezone.now()
        conv.save(update_fields=["ended_at"])
