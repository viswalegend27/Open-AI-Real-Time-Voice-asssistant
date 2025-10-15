import os, json, logging
from dotenv import load_dotenv
from django.utils import timezone
from assistant.models import Conversation, Message, UserPreference, VehicleInterest, Recommendation, ConversationSummary

load_dotenv()
try:
    from openai import OpenAI
    OPENAI_CLIENT = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
except ImportError:
    OPENAI_CLIENT = None

# function used to call OpenAI for chat completions
def openai_chat(prompt, user_content=None, temp=0.2, fmt="json_object"):
    if not OPENAI_CLIENT: return None 
    try:
        msgs = [{"role": "system", "content": prompt}]
        if user_content:
            msgs.append({"role": "user", "content": user_content})
        return json.loads(OPENAI_CLIENT.chat.completions.create(
            model="gpt-4o-mini",
            messages=msgs,
            temperature=temp,
            response_format={"type": fmt}
        ).choices[0].message.content)
    except Exception:
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
    # sending out to OpenAI to get mahindra vehicles list
    fetched = openai_chat(prompt, temp=0.1, fmt="json_object")
    return fetched if fetched and isinstance(fetched, dict) else fallback

def analyze_conversation(session_id):
    # use OpenAI to analyze conversation
    try:
        conv = Conversation.objects.get(session_id=session_id)
        messages = conv.messages.all().order_by('timestamp')
        user_messages = [m.content for m in messages if m.role == 'user']
        all_text = "\n".join(f"Customer: {m}" for m in user_messages)
        prompt = (
            "You are an expert car sales assistant AI. Analyze the customer conversation and return a JSON always containing: "
            '{ "budget": "number + unit or null", "usage": "primary usage (family/adventure/city/commercial) or null", "priority_features": ["list of features"], "vehicle_interest": ["model names or null"], "other_insights": "any relevant note or null" } '
            "Rules: identify only what the customer says, don't guess! Respond only with JSON."
        )
        # gets the extracted preferences from conversation
        extracted = openai_chat(prompt, all_text, temp=0.2) or {}
        logger = logging.getLogger(__name__)
        try:
            # our user preferences DB store
            upds = [
                ('budget', extracted.get('budget')),
                ('usage', extracted.get('usage')),
                ('priority_features', ", ".join(str(f) for f in extracted.get('priority_features', []))) if extracted.get('priority_features') else None
            ]
            # logging each preference being saved if not None
            for ptype, pval in filter(lambda x: x and x[1], upds):
                logger.info(f"Saving {ptype} preference: {pval}")
                # Django ORM update or create
                UserPreference.objects.update_or_create(
                    conversation=conv, preference_type=ptype,
                    defaults={"value": str(pval), "confidence": 0.8}
                )
        except Exception as e:
            logger.error(f"UserPreference DB store error: {e}")
        if extracted.get("vehicle_interest"):
            # our vehicle interest DB store
            for vehicle in extracted["vehicle_interest"]:
                # Django ORM update or create
                VehicleInterest.objects.update_or_create(
                    conversation=conv, vehicle_name=vehicle,
                    defaults={"interest_level":8}
                )
        return {'status': 'success', 'preferences_extracted': conv.preferences.count(), 'extracted': extracted}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def save_message(session_id, role, content, user_id=None):
    conv, _ = Conversation.objects.get_or_create(
        session_id=session_id,
        defaults={'user_id': user_id}
    )
    # conversation message is saved on the basis of role and content
    Message.objects.create(conversation=conv, role=role, content=content)
    conv.total_messages += 1
    conv.save()
    # Always analyze - update preferences every message
    analyze_conversation(session_id)
    return {'status': 'success', 'message_count': conv.total_messages}

def get_recommendations(session_id):
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"get_recommendations() called with session_id={session_id}")
    try:
        # conversation retrieval
        conv = Conversation.objects.get(session_id=session_id)
        logger.info(f"Found Conversation: id={conv.id}")
        # preferences and interests retrieval
        preferences = conv.preferences.all()
        logger.info(f"Preferences found: {[f'{p.preference_type}: {p.value}' for p in preferences]}")
        interests = conv.vehicle_interests.all() # all interests
        logger.info(f"Vehicle Interests: {[v.vehicle_name for v in interests]}")
        vehicles_data = json.dumps(get_mahindra_vehicles())

        # Gather user preferences and vehicle interests
        cleaned_prefs = {p.preference_type: p.value for p in preferences}
        vehicle_interest = [v.vehicle_name for v in interests]

        prompt = f"""
        You are a Mahindra vehicles expert. Match this customer's preferences and interests to Mahindra vehicles: {vehicles_data}
        Preferences: {json.dumps(cleaned_prefs)}
        Interested vehicles: {vehicle_interest}

        Return a JSON object with a single key 'recommendations', whose value is a list of objects. 
        Example format:
        {{
           "recommendations": [
             {{ "vehicle_name": <name>, "why": <reason>, "score": <1-10> }},
             ...
           ]
        }}
        Only recommend from these Mahindra vehicles.
        Be concise and specific. Never return vehicles with score < 5.
        """

        openai_recommendations = []
        if OPENAI_CLIENT:
            response = OPENAI_CLIENT.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an assistant that recommends Mahindra vehicles given preferences. Always output a JSON object with a 'recommendations' array as described."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.25,
                response_format={"type": "json_object"},
            )
            ai_content = json.loads(response.choices[0].message.content)
            openai_recommendations = ai_content.get('recommendations', [])
            logger.info(f"OpenAI recommendations returned: {openai_recommendations}")
        else:
            # Fallback (static)
            for vehicle in get_mahindra_vehicles():
                if not cleaned_prefs or vehicle in vehicle_interest:
                    openai_recommendations.append({"vehicle_name": vehicle, "why": "In fallback mode.", "score": 5})
            logger.info(f"Fallback recommendations: {openai_recommendations}")

        recs_result = []
        features = cleaned_prefs.get('priority_features', '').split(', ') if cleaned_prefs.get('priority_features') else []
        for rec in openai_recommendations:
            try:
                obj, created = Recommendation.objects.update_or_create(
                    conversation=conv,
                    vehicle_name=rec.get("vehicle_name"),
                    defaults={
                        'match_score': rec.get("score", 5),
                        'reason': rec.get("why", "Relevant to your preferences"),
                        'features_matched': features
                    }
                )
                logger.info(f"Recommendation saved: {obj.vehicle_name}, created={created}")
            except Exception as rec_exception:
                logger.error(f"Error saving recommendation for {rec.get('vehicle_name')}: {rec_exception}")
            recs_result.append({'vehicle': rec.get("vehicle_name"), 'score': rec.get("score", 5)})
        logger.info(f"Recommendation process complete for session_id={session_id}")
        return {'status': 'success', 'recommendations': sorted(recs_result, key=lambda x: x['score'], reverse=True)}
    except Exception as e:
        logger.error(f"get_recommendations failed: {e}")
        return {'status': 'error', 'message': str(e)}

def generate_conversation_summary(session_id):
    try:
        conv = Conversation.objects.get(session_id=session_id)
        messages = conv.messages.all().order_by('timestamp')

        if messages.count() == 0:
            return {'status': 'error', 'message': 'No messages found'}

        # Build conversation transcript
        transcript = ""
        for msg in messages:
            role_label = "Customer" if msg.role == "user" else "Ishmael"
            transcript += f"{role_label}: {msg.content}\n\n"

        # Get existing analysis data
        preferences = conv.preferences.all()
        interests = conv.vehicle_interests.all()
        recommendations = conv.recommendations.all().order_by('-match_score')

        # Create prompt for AI summary
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

        # Generate summary using OpenAI or fallback
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
                "summary": f"Conversation with {messages.count()} messages. Customer showed interest in Mahindra vehicles.",
                "customer_name": None,
                "contact_info": None,
                "budget_range": preferences.filter(preference_type='budget').first().value if preferences.filter(preference_type='budget').exists() else None,
                "vehicle_type": "SUV" if interests.exists() else None,
                "use_case": preferences.filter(preference_type='usage').first().value if preferences.filter(preference_type='usage').exists() else None,
                "priority_features": [],
                "recommended_vehicles": [r.vehicle_name for r in recommendations[:3]],
                "next_actions": ["Follow up with customer", "Schedule test drive"],
                "sentiment": "positive",
                "engagement_score": 7,
                "purchase_intent": "medium"
            }

        # Save summary to database
        summary, _ = ConversationSummary.objects.update_or_create(
            conversation=conv,
            defaults={
                'summary_text': summary_data.get('summary', ''),
                'customer_name': summary_data.get('customer_name'),
                'contact_info': summary_data.get('contact_info'),
                'budget_range': summary_data.get('budget_range'),
                'vehicle_type': summary_data.get('vehicle_type'),
                'use_case': summary_data.get('use_case'),
                'priority_features': summary_data.get('priority_features', []),
                'recommended_vehicles': summary_data.get('recommended_vehicles', []),
                'next_actions': summary_data.get('next_actions', []),
                'sentiment': summary_data.get('sentiment'),
                'engagement_score': summary_data.get('engagement_score', 5),
                'purchase_intent': summary_data.get('purchase_intent')
            }
        )

        # Mark conversation as ended
        if not conv.ended_at:
            conv.ended_at = timezone.now()
            conv.save()

        # Create a user-friendly formatted summary
        formatted_summary = format_summary_for_user(summary_data, conv, preferences, interests, recommendations)

        return {
            'status': 'success',
            'summary': summary_data,
            'summary_id': summary.id,
            'formatted_summary': formatted_summary
        }

    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def format_summary_for_user(summary_data, conversation, preferences, interests, recommendations):
    parts = []

    # Budget
    budget_pref = preferences.filter(preference_type='budget').first()
    budget = budget_pref.value if budget_pref else summary_data.get('budget_range')
    if budget:
        parts.append(f"Budget: {budget}")

    # Use case
    usage_pref = preferences.filter(preference_type='usage').first()
    use_case = usage_pref.value if usage_pref else summary_data.get('use_case')
    if use_case:
        parts.append(f"Use: {use_case}")

    # Interested vehicles
    if interests.exists():
        vehicles = [interest.vehicle_name for interest in interests.order_by('-interest_level')[:2]]
        parts.append(f"Interested in: {', '.join(vehicles)}")

    # Top recommendation
    if recommendations.exists():
        top_rec = recommendations.order_by('-match_score').first()
        parts.append(f"Top match: {top_rec.vehicle_name}")

    return " | ".join(parts) if parts else "No preferences captured yet"