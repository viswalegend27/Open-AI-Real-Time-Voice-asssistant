from django.db import models
from django.utils import timezone

class Conversation(models.Model): 
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    user_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    total_messages = models.IntegerField(default=0)
    messages_json = models.JSONField(default=list)
    # Store summary info directly here.
    summary_data = models.JSONField(default=dict, blank=True)
    summary_generated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Conversation {self.session_id[:8]} - {self.started_at}"

class UserPreference(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='preferences')
    data = models.JSONField(default=dict)
    extracted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-extracted_at']

    def __str__(self):
        return f"{self.data.get('type', '?')}: {self.data.get('value', '?')}"

class VehicleInterest(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='vehicle_interests')
    vehicle_name = models.CharField(max_length=100, db_index=True)
    meta = models.JSONField(default=dict)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return self.vehicle_name
