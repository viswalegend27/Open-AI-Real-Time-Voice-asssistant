# analyzer.py
import os
import json
import logging
from dotenv import load_dotenv
from django.utils import timezone
from assistant.models import Conversation, UserPreference, VehicleInterest, ConversationSummary
from celery import shared_task

load_dotenv()

try:
    from openai import OpenAI
    OPENAI_CLIENT = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
except ImportError:
    OPENAI_CLIENT = None

def openai_chat(prompt, user_content=None, temp=0.2, fmt="json_object"):
    """Utility to query OpenAI for JSON response."""
    if not OPENAI_CLIENT:
        return None
    try:
        msgs = [{"role": "system", "content": prompt}]
        if user_content:
            msgs.append({"role": "user", "content": user_content})
        resp = OPENAI_CLIENT.chat.completions.create(
            model="gpt-4o-mini",
            messages=msgs,
            temperature=temp,
            response_format={"type": fmt}
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logging.getLogger(__name__).error(f"openai_chat error: {e}")
        return None

def get_mahindra_vehicles():
    prompt = (
        "You are an expert on Mahindra vehicles. "
        "List all major Mahindra passenger vehicles currently on sale in India, with their type, segment, and top features. "
        "Return a JSON mapping: { 'ModelName': { 'type': 'SUV/EV/etc', 'segment': 'premium/compact/etc', 'features': ['feature', ...] }, ... }. "
        "Return only what is real and don't invent new models."
    )
    fallback = {
        'XUV700': {'type': 'SUV', 'segment': 'premium', 'features': ['luxury', 'tech', 'safety', 'family', 'spacious']},
        'Scorpio-N': {'type': 'SUV', 'segment': 'premium', 'features': ['powerful', 'rugged', 'commanding', 'spacious']},
        'Thar': {'type': 'SUV', 'segment': 'lifestyle', 'features': ['offroad', 'adventure', 'iconic', 'rugged']},
        'XUV400': {'type': 'EV', 'segment': 'compact', 'features': ['electric', 'eco-friendly', 'modern', 'city']},
        'XUV300': {'type': 'SUV', 'segment': 'compact', 'features': ['city', 'stylish', 'compact', 'efficient']},
        'Scorpio Classic': {'type': 'SUV', 'segment': 'workhorse', 'features': ['reliable', 'tough', 'value']},
        'Bolero': {'type': 'SUV', 'segment': 'commercial', 'features': ['tough', 'reliable', 'rural', 'commercial']},
    }
    fetched = openai_chat(prompt, temp=0.1, fmt="json_object")
    return fetched if fetched and isinstance(fetched, dict) else fallback

def analyze_conversation(session_id):
    try:
        conv = Conversation.objects.get(session_id=session_id)
        messages = conv.messages_json or []
        user_messages = [m['content'] for m in messages if m['role'] == 'user']
        all_text = "\n".join(f"Customer: {m}" for m in user_messages)

        prompt = (
            "You are an expert car sales assistant AI. Analyze the customer conversation and return a JSON always containing: "
            '{ "budget": "number + unit or null", "usage": "primary usage (family/adventure/city/commercial) or null", "priority_features": ["list of features"], "vehicle_interest": ["model names or null"], "other_insights": "any relevant note or null" } '
            "Rules: identify only what the customer says, don't guess! Respond only with JSON."
        )
        extracted = openai_chat(prompt, all_text, temp=0.2) or {}
        logger = logging.getLogger(__name__)

        upds = [
            ('budget', extracted.get('budget')),
            ('usage', extracted.get('usage')),
            ('priority_features', ", ".join(str(f) for f in extracted.get('priority_features', [])) if extracted.get('priority_features') else None)
        ]

        for ptype, pval in filter(lambda x: x[1] is not None, upds):
            logger.info(f"Saving {ptype} preference: {pval}")
            UserPreference.objects.update_or_create(
                conversation=conv, data__type=ptype,
                defaults={
                    "data": {"type": ptype, "value": str(pval), "confidence": 0.8},
                    "extracted_at": timezone.now()
                }
            )

        if extracted.get("vehicle_interest"):
            for vehicle in extracted["vehicle_interest"]:
                VehicleInterest.objects.update_or_create(
                    conversation=conv, vehicle_name=vehicle,
                    defaults={
                        "meta": {"interest_level": 8},
                        "timestamp": timezone.now()
                    }
                )
        return {'status': 'success', 'preferences_extracted': conv.preferences.count(), 'extracted': extracted}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def save_message(session_id, role, content, user_id=None):
    # Analyze and save a message to the conversation. Our analyze conversation function is called here.
    conv, _ = Conversation.objects.get_or_create(session_id=session_id, defaults={'user_id': user_id})
    conv.refresh_from_db()
    messages = list(conv.messages_json or [])
    messages.append({
        'role': role,
        'content': content,
        'timestamp': timezone.now().isoformat()
    })
    conv.messages_json = messages
    conv.total_messages = len(messages)
    conv.save(update_fields=['messages_json', 'total_messages'])
    analyze_conversation(session_id)
    return {'status': 'success', 'message_count': conv.total_messages}

def generate_conversation_summary(session_id):
    try:
        conv = Conversation.objects.get(session_id=session_id)
        messages = conv.messages_json or []
        if not messages:
            return {'status': 'error', 'message': 'No messages found'}

        transcript = "\n".join(f"{'Customer' if m['role'] == 'user' else 'Ishmael'}: {m['content']}" for m in messages)

        preferences = conv.preferences.all()
        interests = conv.vehicle_interests.all()

        prompt = f"""You are analyzing a completed sales conversation. Extract key information and insights.
CONVERSATION:
{transcript}
Analyze this conversation and return a JSON object with:
{{
"summary": "2-3 sentences describing what the customer wants and the conversation outcome",
"customer_name": "name if mentioned, else null",
"contact_info": "phone/email if mentioned, else null",
"budget_range": "exact budget mentioned (e.g. '20 lakhs', '15-18 lakhs'), else null",
"vehicle_type": "SUV/EV/Sedan based on interest shown",
"use_case": "family/adventure/city/commercial based on conversation",
"priority_features": ["list 3-5 features customer mentioned caring about"],
"recommended_vehicles": ["list specific Mahindra vehicles discussed - Thar, XUV700, Scorpio-N, etc."],
"next_actions": ["2-3 specific action items for sales follow-up"],
"sentiment": "positive/neutral/negative - customer's overall tone",
"engagement_score": "1-10 based on conversation depth and interest",
"purchase_intent": "high/medium/low based on buying signals"
}}
RULES:
- Be specific - extract actual details from conversation
- Don't invent information - use null if not mentioned
- recommended_vehicles should only include vehicles the customer showed interest in
- next_actions should be practical and specific
- Focus on what the customer WANTS, not what Ishmael said"""

        if OPENAI_CLIENT:
            response = OPENAI_CLIENT.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing sales conversations and extracting key information. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            summary_data = json.loads(response.choices[0].message.content)
        else:
            summary_data = {
                "summary": f"Conversation with {len(messages)} messages. Customer showed interest in Mahindra vehicles.",
                "customer_name": None,
                "contact_info": None,
                "budget_range": None,
                "vehicle_type": "SUV" if interests.exists() else None,
                "use_case": None,
                "priority_features": [],
                "recommended_vehicles": [],
                "next_actions": ["Follow up with customer", "Schedule test drive"],
                "sentiment": "positive",
                "engagement_score": 7,
                "purchase_intent": "medium"
            }

        for pref in preferences:
            if pref.data.get('type') == 'budget' and summary_data['budget_range'] is None:
                summary_data['budget_range'] = pref.data.get('value')
            elif pref.data.get('type') == 'usage' and summary_data['use_case'] is None:
                summary_data['use_case'] = pref.data.get('value')

        summary, _ = ConversationSummary.objects.update_or_create(
            conversation=conv,
            defaults={'data': summary_data, 'generated_at': timezone.now()}
        )

        if not conv.ended_at:
            conv.ended_at = timezone.now()
            conv.save()

        formatted_summary = format_summary_for_user(summary_data, conv, preferences, interests)
        return {
            'status': 'success',
            'summary': summary_data,
            'summary_id': summary.id,
            'formatted_summary': formatted_summary
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@shared_task
def generate_summary_task(session_id):
    return generate_conversation_summary(session_id)

def format_summary_for_user(summary_data, conversation, preferences, interests):
    parts = []
    budget = use_case = None
    for pref in preferences:
        if pref.data.get('type') == 'budget':
            budget = pref.data.get('value')
        elif pref.data.get('type') == 'usage':
            use_case = pref.data.get('value')
    if budget:
        parts.append(f"Budget: {budget}")
    if use_case:
        parts.append(f"Use: {use_case}")
    if interests.exists():
        best_interests = interests.order_by('-meta__interest_level')[:2]
        vehicles = [interest.vehicle_name for interest in best_interests]
        parts.append(f"Interested in: {', '.join(vehicles)}")
    return " | ".join(parts) if parts else "No preferences captured yet"