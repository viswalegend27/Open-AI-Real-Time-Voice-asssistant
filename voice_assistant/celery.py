import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_assistant.settings')

app = Celery('voice_assistant')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()