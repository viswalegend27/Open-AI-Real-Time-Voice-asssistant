import os
import json
import logging
from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings
from assistant.models import Conversation
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task
def send_conversation_summary(session_id):
    logger.info("[CELERY TASK] send_conversation_summary called for session_id=%s", session_id)
    recipient = os.environ.get('MAIN_EMAIL')
    # Fetch conversation!
    try:
        conv = Conversation.objects.get(session_id=session_id)
        summary_text = json.dumps(conv.summary_data, indent=2, ensure_ascii=False)
        email = EmailMessage(
            'Your Conversation Summary',
            'Attached is your conversation summary.',
            settings.EMAIL_HOST_USER,
            [recipient],
        )
        email.attach('conversation_summary.txt', summary_text, 'text/plain')
        email.send()
        # Mark as sent
        conv.summary_emailed_at = timezone.now()
        conv.save(update_fields=["summary_emailed_at"])
        logger.info(f"Summary email for conversation {session_id} sent to {recipient}")
    except Conversation.DoesNotExist:
        logger.error("Conversation %s not found.", session_id)

@shared_task
def scheduled_summaries_for_open_conversations():
    conv = Conversation.objects.exclude(
        Q(summary_data__isnull=True) | Q(summary_data={}) | Q(summary_emailed_at__isnull=False)
    ).order_by('-started_at').first()
    if not conv:
        logger.info("[CELERY BEAT] No conversations with completed summary to mail.")
        return

    logger.info(f"[CELERY BEAT] Mailing summary for conversation {conv.session_id}")
    # Only pass session_id!
    send_conversation_summary.apply_async(args=[conv.session_id], countdown=5)