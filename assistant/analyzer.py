import os
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from django.utils import timezone
from django.db import transaction
from celery import shared_task
from assistant.models import Conversation, UserPreference, VehicleInterest
from assistant.tools import conversation_summary_schema, conversation_analysis_schema

load_dotenv()

try:
    from openai import OpenAI
    OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    OPENAI_CLIENT = None

# function wrapper to call the openAI
def _call_openai(messages: List[Dict[str, str]],
                 functions: Optional[List[Dict[str, Any]]] = None,
                 function_name: Optional[str] = None,
                 model: str = "gpt-4o-mini",
                 temperature: float = 0.2) -> Optional[Dict[str, Any]]:
    if not OPENAI_CLIENT:
        return None
    try:
        resp = OPENAI_CLIENT.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            functions=functions or [],
            function_call={"name": function_name} if function_name else None,
            response_format={"type": "json_object"},
        )
        choice = resp.choices[0].message
        # prefer function_call.arguments if present
        if getattr(choice, "function_call", None) and getattr(choice.function_call, "arguments", None):
            return json.loads(choice.function_call.arguments)
        # fallback: message content might be json
        if getattr(choice, "content", None):
            try:
                return json.loads(choice.content)
            except Exception:
                return None
    except Exception:
        return None
    return None

def _user_texts(conv: Conversation) -> List[str]:
    return [m.get("content") for m in (conv.messages_json or []) if m.get("role") == "user" and m.get("content")]

@shared_task
def generate_summary_task(session_id: str):
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

    messages = [
        {"role": "system",
        "content": ("You are a Mahindra car sales assistant AI. Extract user needs according to the schema. "
                    "Return only a valid JSON object as your output.")},
        {"role": "user", "content": all_text},
    ]
    # my tool call occurs here
    extracted = _call_openai(messages,functions=[conversation_analysis_schema],function_name="analyze_customer_preferences") or {}

    # persist results concisely
    try:
        with transaction.atomic():
            # save simple preferences
            for key in ("budget", "usage"):
                val = extracted.get(key)
                if val:
                    UserPreference.objects.update_or_create(
                        conversation=conv,
                        data__type=key,
                        defaults={"data": {"type": key, "value": str(val), "confidence": 0.8},
                                  "extracted_at": timezone.now()}
                    )

            # priority features
            pf = extracted.get("priority_features")
            if pf:
                UserPreference.objects.update_or_create(
                    conversation=conv,
                    data__type="priority_features",
                    defaults={"data": {"type": "priority_features", "value": json.dumps(pf), "confidence": 0.7},
                              "extracted_at": timezone.now()}
                )

            # vehicle interests: bulk create new, update existing
            vehicles = [v for v in (extracted.get("vehicle_interest") or []) if v]
            if vehicles:
                existing = set(VehicleInterest.objects.filter(conversation=conv, vehicle_name__in=vehicles)
                               .values_list("vehicle_name", flat=True))
                now = timezone.now()
                to_create = [VehicleInterest(conversation=conv, vehicle_name=v,
                                             meta={"interest_level": 8}, timestamp=now)
                             for v in vehicles if v not in existing]
                if to_create:
                    VehicleInterest.objects.bulk_create(to_create)
                VehicleInterest.objects.filter(conversation=conv, vehicle_name__in=vehicles).update(
                    meta={"interest_level": 8}, timestamp=now
                )
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

    transcript = "\n".join(
        f"{'Customer' if m['role'] == 'user' else 'Ishmael'}: {m['content']}"
        for m in msgs
    )

    messages = [
        {"role": "system",
        "content": ("You are an expert Mahindra sales assistant. Summarize the conversation per schema. "
                    "Return your answer as a JSON object.")},
        {"role": "user", "content": transcript},
    ]

    summary_data = _call_openai(messages,functions=[conversation_summary_schema],function_name="summarize_sales_conversation") or {}
    
    for pref in conv.preferences.all():
        if pref.data.get("type") == "budget" and not summary_data.get("budget_range"):
            summary_data["budget_range"] = pref.data.get("value")
        if pref.data.get("type") == "usage" and not summary_data.get("use_case"):
            summary_data["use_case"] = pref.data.get("value")

    conv.summary_data = summary_data
    conv.summary_generated_at = timezone.now()
    if not conv.ended_at:
        conv.ended_at = timezone.now()
    conv.save(update_fields=["summary_data", "summary_generated_at", "ended_at"])

    return summary_data
