"""Conversation intelligence analyzer and recommendation engine"""

from assistant.models import Conversation, Message, UserPreference, VehicleInterest, Recommendation, ConversationSummary
import re
import os
import json
from dotenv import load_dotenv

load_dotenv()

# OpenAI API setup for summary generation
try:
    from openai import OpenAI
    OPENAI_CLIENT = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
except ImportError:
    OPENAI_CLIENT = None

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
    """Analyze conversation to extract budget, preferences, and vehicle interests
    
    Args:
        session_id: Unique conversation session identifier
        
    Returns:
        dict: Status and count of preferences extracted
    """
    try:
        conv = Conversation.objects.get(session_id=session_id)
        messages = conv.messages.all()
        
        user_messages = [m.content.lower() for m in messages if m.role == 'user']
        all_text = ' '.join(user_messages)
        
        budget_match = re.search(r'(\d+)\s*(lakh|lakhs|l)', all_text)
        if budget_match:
            UserPreference.objects.get_or_create(
                conversation=conv,
                preference_type='budget',
                defaults={'value': budget_match.group(0), 'confidence': 0.8}
            )
        
        if any(word in all_text for word in ['family', 'kids', 'children', 'parents']):
            UserPreference.objects.get_or_create(
                conversation=conv,
                preference_type='usage',
                defaults={'value': 'family', 'confidence': 0.7}
            )
        elif any(word in all_text for word in ['adventure', 'offroad', 'trek', 'travel']):
            UserPreference.objects.get_or_create(
                conversation=conv,
                preference_type='usage',
                defaults={'value': 'adventure', 'confidence': 0.7}
            )
        elif any(word in all_text for word in ['city', 'urban', 'commute']):
            UserPreference.objects.get_or_create(
                conversation=conv,
                preference_type='usage',
                defaults={'value': 'city', 'confidence': 0.7}
            )
        
        for vehicle, data in MAHINDRA_VEHICLES.items():
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

def get_recommendations(session_id):
    """Generate vehicle recommendations based on extracted preferences
    
    Args:
        session_id: Unique conversation session identifier
        
    Returns:
        dict: Status and list of recommended vehicles with scores
    """
    try:
        conv = Conversation.objects.get(session_id=session_id)
        prefs = conv.preferences.all()
        interests = conv.vehicle_interests.all()
        
        recommendations = []
        
        usage = prefs.filter(preference_type='usage').first()
        if usage:
            for vehicle, data in MAHINDRA_VEHICLES.items():
                score = 0
                matched_features = []
                
                if usage.value in data['features']:
                    score += 30
                    matched_features.append(usage.value)
                
                if interests.filter(vehicle_name=vehicle).exists():
                    interest_obj = interests.get(vehicle_name=vehicle)
                    score += interest_obj.interest_level * 5
                
                if usage.value == 'adventure' and data['type'] == 'SUV':
                    score += 20
                elif usage.value == 'city' and data['segment'] == 'compact':
                    score += 25
                elif usage.value == 'family' and 'spacious' in data['features']:
                    score += 20
                    matched_features.append('spacious')
                
                if score > 20:
                    Recommendation.objects.update_or_create(
                        conversation=conv,
                        vehicle_name=vehicle,
                        defaults={
                            'match_score': score,
                            'reason': f"Matches your {usage.value} needs",
                            'features_matched': matched_features
                        }
                    )
                    recommendations.append({'vehicle': vehicle, 'score': score})
        
        return {'status': 'success', 'recommendations': sorted(recommendations, key=lambda x: x['score'], reverse=True)}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def save_message(session_id, role, content, user_id=None):
    """Save conversation message and trigger analysis every 3 messages
    
    Args:
        session_id: Unique conversation session identifier
        role: Message role (user/assistant)
        content: Message content
        user_id: Optional user identifier
        
    Returns:
        dict: Status and current message count
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
    """Generate AI-powered conversation summary with key details
    
    Args:
        session_id: Unique conversation session identifier
        
    Returns:
        dict: Status and summary data
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
        
        # Generate summary using OpenAI
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
            # Fallback summary if OpenAI not available
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
        summary, created = ConversationSummary.objects.update_or_create(
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
        from django.utils import timezone
        if not conv.ended_at:
            conv.ended_at = timezone.now()
            conv.save()
        
        # Create a user-friendly formatted summary
        formatted_summary = format_summary_for_user(summary_data, conv, preferences, interests, recommendations)
        
        return {
            'status': 'success',
            'summary': summary_data,
            'summary_id': summary.id,
            'formatted_summary': formatted_summary  # Add user-friendly version
        }
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def format_summary_for_user(summary_data, conversation, preferences, interests, recommendations):
    """Format the summary in a user-friendly, conversational way
    
    Args:
        summary_data: AI-generated summary dictionary
        conversation: Conversation object
        preferences: QuerySet of UserPreference objects
        interests: QuerySet of VehicleInterest objects
        recommendations: QuerySet of Recommendation objects
        
    Returns:
        str: Nicely formatted summary text for the user
    """
    lines = []
    lines.append("\n=== 🚗 CONVERSATION SUMMARY ===")
    lines.append("")
    
    # Main summary
    if summary_data.get('summary'):
        lines.append(f"📋 {summary_data['summary']}")
        lines.append("")
    
    # Customer details
    if summary_data.get('customer_name') or summary_data.get('contact_info'):
        lines.append("👤 CUSTOMER DETAILS:")
        if summary_data.get('customer_name'):
            lines.append(f"   Name: {summary_data['customer_name']}")
        if summary_data.get('contact_info'):
            lines.append(f"   Contact: {summary_data['contact_info']}")
        lines.append("")
    
    # Requirements from database
    if preferences.exists() or summary_data.get('budget_range') or summary_data.get('vehicle_type') or summary_data.get('use_case'):
        lines.append("🎯 YOUR REQUIREMENTS:")
        
        # Budget from DB or summary
        budget_pref = preferences.filter(preference_type='budget').first()
        budget = budget_pref.value if budget_pref else summary_data.get('budget_range')
        if budget:
            lines.append(f"   💰 Budget: {budget}")
        
        # Vehicle type
        if summary_data.get('vehicle_type'):
            lines.append(f"   🚙 Vehicle Type: {summary_data['vehicle_type']}")
        
        # Use case from DB or summary
        usage_pref = preferences.filter(preference_type='usage').first()
        use_case = usage_pref.value if usage_pref else summary_data.get('use_case')
        if use_case:
            lines.append(f"   🎯 Primary Use: {use_case.title()}")
        
        # Priority features
        if summary_data.get('priority_features'):
            features = ', '.join(summary_data['priority_features'])
            lines.append(f"   ⭐ Important Features: {features}")
        
        lines.append("")
    
    # Vehicle interests from database
    if interests.exists():
        lines.append("💚 VEHICLES YOU'RE INTERESTED IN:")
        for interest in interests.order_by('-interest_level'):
            vehicle_data = MAHINDRA_VEHICLES.get(interest.vehicle_name, {})
            vehicle_type = vehicle_data.get('type', 'Vehicle')
            lines.append(f"   • {interest.vehicle_name} ({vehicle_type}) - Interest Level: {interest.interest_level}/10")
        lines.append("")
    
    # Recommendations from database
    if recommendations.exists():
        lines.append("🎖️ MY RECOMMENDATIONS FOR YOU:")
        for idx, rec in enumerate(recommendations.order_by('-match_score')[:3], 1):
            lines.append(f"   {idx}. {rec.vehicle_name} (Match Score: {rec.match_score:.0f}%)")
            lines.append(f"      Reason: {rec.reason}")
            if rec.features_matched:
                lines.append(f"      Matched Features: {', '.join(rec.features_matched)}")
        lines.append("")
    elif summary_data.get('recommended_vehicles'):
        # Fallback to AI summary if DB recommendations not available
        lines.append("🎖️ VEHICLES DISCUSSED:")
        for vehicle in summary_data['recommended_vehicles']:
            lines.append(f"   • {vehicle}")
        lines.append("")
    
    # Next steps
    if summary_data.get('next_actions'):
        lines.append("📅 NEXT STEPS:")
        for idx, action in enumerate(summary_data['next_actions'], 1):
            lines.append(f"   {idx}. {action}")
        lines.append("")
    
    # Engagement metrics
    if summary_data.get('sentiment') or summary_data.get('purchase_intent'):
        lines.append("📊 ENGAGEMENT INSIGHTS:")
        if summary_data.get('sentiment'):
            sentiment_emoji = {"positive": "😊", "neutral": "😐", "negative": "😞"}.get(summary_data['sentiment'], "")
            lines.append(f"   Sentiment: {sentiment_emoji} {summary_data['sentiment'].title()}")
        if summary_data.get('engagement_score'):
            lines.append(f"   Engagement Score: {summary_data['engagement_score']}/10")
        if summary_data.get('purchase_intent'):
            lines.append(f"   Purchase Intent: {summary_data['purchase_intent'].title()}")
        lines.append("")
    
    # Conversation stats
    lines.append(f"💬 Total Messages: {conversation.total_messages}")
    if conversation.ended_at:
        duration = (conversation.ended_at - conversation.started_at).total_seconds() / 60
        lines.append(f"⏱️ Duration: {duration:.1f} minutes")
    
    lines.append("\n=== END OF SUMMARY ===")
    
    return "\n".join(lines)
