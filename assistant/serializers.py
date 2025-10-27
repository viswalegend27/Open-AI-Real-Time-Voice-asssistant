from rest_framework import serializers
from .models import Conversation, VehicleInterest

class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = [
            'session_id',
            'user_id',
            'started_at',
            'ended_at',
            'total_messages',
            'messages_json',
            'summary_data',
            'summary_generated_at'
        ]

class SummarySerializer(serializers.Serializer):
    text = serializers.CharField(source="summary", allow_blank=True, required=False)
    customer_name = serializers.CharField(allow_blank=True, required=False)
    contact_info = serializers.CharField(allow_blank=True, required=False)
    budget_range = serializers.CharField(allow_blank=True, required=False)
    vehicle_type = serializers.CharField(allow_blank=True, required=False)
    use_case = serializers.CharField(allow_blank=True, required=False)
    priority_features = serializers.ListField(child=serializers.CharField(), required=False)
    recommended_vehicles = serializers.ListField(child=serializers.CharField(), required=False)
    next_actions = serializers.ListField(child=serializers.CharField(), required=False)
    sentiment = serializers.CharField(allow_blank=True, required=False)
    engagement_score = serializers.FloatField(required=False, allow_null=True)
    purchase_intent = serializers.CharField(allow_blank=True, required=False)
    generated_at = serializers.DateTimeField(required=False, allow_null=True)

class ConversationShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = [
            "session_id",
            "started_at",
            "ended_at",
            "total_messages"
        ]

class VehicleInterestSerializer(serializers.ModelSerializer):
    interest_level = serializers.SerializerMethodField()
    mentioned_features = serializers.SerializerMethodField()
    conversation_id = serializers.CharField(source='conversation.session_id')
    user_id = serializers.CharField(source='conversation.user_id')

    class Meta:
        model = VehicleInterest
        fields = [
            "id",
            "vehicle_name",
            "interest_level",
            "mentioned_features",
            "timestamp",
            "conversation_id",
            "user_id"
        ]

    def get_interest_level(self, obj):
        return obj.meta.get("interest_level")

    def get_mentioned_features(self, obj):
        return obj.meta.get("mentioned_features", [])
