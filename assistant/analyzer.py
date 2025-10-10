"""Conversation intelligence analyzer and recommendation engine"""

import re
import os
import json
from dotenv import load_dotenv
from assistant.models import (
    Conversation, Message, UserPreference, VehicleInterest, Recommendation, ConversationSummary
)
from django.utils import timezone

load_dotenv()

# OpenAI API setup for summary generation
try:
    from openai import OpenAI
    OPENAI_CLIENT = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
except ImportError:
    OPENAI_CLIENT = None

# Mahindra vehicle feature index
MAHINDRA_VEHICLES = {
    'XUV700': {'type': 'SUV', 'segment': 'premium', 'features': ['luxury', 'tech', 'safety', 'family', 'spacious']},
    'Scorpio-N': {'type': 'SUV', 'segment': 'premium', 'features': ['powerful', 'rugged', 'commanding', 'spacious']},
    'Thar': {'type': 'SUV', 'segment': 'lifestyle', 'features': ['offroad', 'adventure', 'iconic', 'rugged']},
    'XUV400': {'type': 'EV', 'segment': 'compact', 'features': ['electric', 'eco-friendly', 'modern', 'city']},
    'XUV300': {'type': 'SUV', 'segment': 'compact', 'features': ['city', 'stylish', 'compact', 'efficient']},
    'Scorpio Classic': {'type': 'SUV', 'segment': 'workhorse', 'features': ['reliable', 'tough', 'value']},
    'Bolero': {'type': 'SUV', 'segment': 'commercial', 'features': ['tough', 'reliable', 'rural', 'commercial']},
}

def analyze_conversation(session_id):
    """
    Analyze conversation to extract user's budget, preferences, and vehicle interests.
    """
    try:
        conv = Conversation.objects.get(session_id=session_id)
        messages = conv.messages.all()
        user_messages = [m.content.lower() for m in messages if m.role == 'user']
        all_text = " ".join(user_messages)

        # Extract budget
        budget_match = re.search(r"(\d+)\s*(lakh|lakhs|l)", all_text)
        if budget_match:
            UserPreference.objects.get_or_create(
                conversation=conv,
                preference_type='budget',
                defaults={'value': budget_match.group(0), 'confidence': 0.8}
            )

        # Extract use case
        usage_keywords = [
            (['family', 'kids', 'children', 'parents'], 'family'),
            (['adventure', 'offroad', 'trek', 'travel'], 'adventure'),
            (['city', 'urban', 'commute'], 'city'),
        ]
        for keywords, usage_value in usage_keywords:
            if any(word in all_text for word in keywords):
                UserPreference.objects.get_or_create(
                    conversation=conv,
                    preference_type='usage',
                    defaults={'value': usage_value, 'confidence': 0.7}
                )
                break

        # Extract vehicle interest
        for vehicle in MAHINDRA_VEHICLES:
            if vehicle.lower() in all_text:
                interest = all_text.count(vehicle.lower())
                VehicleInterest.objects.update_or_create(
                    conversation=conv,
                    vehicle_name=vehicle,
                    defaults={'interest_level': min(10, interest * 3 + 5)}
                )

        return {'status': 'success', 'preferences_extracted': conv.preferences.count()}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def save_message(session_id, role, content, user_id=None):
    """
    Save conversation message and trigger analysis every 3 messages.
    """
    conv, created = Conversation.objects.get_or_create(
        session_id=session_id,
        defaults={'user_id': user_id}
    )
    Message.objects.create(
        conversation=conv,
        role=role,
        content=content
    )
    conv.total_messages += 1
    conv.save()
    if conv.total_messages % 3 == 0:
        analyze_conversation(session_id)
    return {'status': 'success', 'message_count': conv.total_messages}

def generate_conversation_summary(session_id):
    """
    Generate AI-powered conversation summary with key details.
    """
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
    """
    Format a concise, conversational summary for the UI.
    """
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