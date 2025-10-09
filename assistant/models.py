"""Database models for Mahindra Voice Assistant"""

from django.db import models
from django.utils import timezone

class Conversation(models.Model):
    """Stores conversation metadata and session information"""
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    user_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    total_messages = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-started_at']
        
    def __str__(self):
        return f"Conversation {self.session_id[:8]} - {self.started_at}"

class Message(models.Model):
    """Stores individual conversation messages"""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['timestamp']
        
    def __str__(self):
        return f"{self.role}: {self.content[:50]}"

class UserPreference(models.Model):
    """Stores extracted user preferences (budget, usage, etc.)"""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='preferences')
    preference_type = models.CharField(max_length=50, db_index=True)
    value = models.TextField()
    confidence = models.FloatField(default=0.5)
    extracted_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-confidence', '-extracted_at']
        
    def __str__(self):
        return f"{self.preference_type}: {self.value}"

class VehicleInterest(models.Model):
    """Tracks user interest in specific vehicles"""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='vehicle_interests')
    vehicle_name = models.CharField(max_length=100, db_index=True)
    interest_level = models.IntegerField(default=5, choices=[(i, str(i)) for i in range(1, 11)])
    mentioned_features = models.JSONField(default=list)
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-interest_level', '-timestamp']
        
    def __str__(self):
        return f"{self.vehicle_name} - Interest: {self.interest_level}/10"

class Recommendation(models.Model):
    """Stores AI-generated vehicle recommendations"""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='recommendations')
    vehicle_name = models.CharField(max_length=100)
    reason = models.TextField()
    match_score = models.FloatField()
    features_matched = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-match_score', '-created_at']
        
    def __str__(self):
        return f"{self.vehicle_name} - Score: {self.match_score}"
