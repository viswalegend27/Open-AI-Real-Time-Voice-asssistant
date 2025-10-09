"""Conversation intelligence analyzer and recommendation engine"""

from assistant.models import Conversation, Message, UserPreference, VehicleInterest, Recommendation
import re

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
