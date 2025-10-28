import os
import json
import logging
from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings
from assistant.models import Conversation

logger = logging.getLogger(__name__)

@shared_task
def send_conversation_summary(summary_text):
    logger.info("[CELERY TASK] send_conversation_summary called")
    print("[CELERY TASK] send_conversation_summary called")
    file_path = os.path.join(settings.BASE_DIR, 'conversation_summary.txt')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    recipient = os.environ.get('MAIN_EMAIL')
    if not recipient:
        logger.error("MAIN_EMAIL environment variable is not set.")
        raise Exception("MAIN_EMAIL environment variable is not set.")
    email = EmailMessage(
        'Your Conversation Summary',
        'Attached is your conversation summary as a text file.',
        settings.EMAIL_HOST_USER,
        [recipient],
    )
    email.attach_file(file_path)
    email.send()
    logger.info(f"Summary email sent to {recipient}")
    print(f"Summary email sent to {recipient}")
    os.remove(file_path)

@shared_task
def scheduled_summaries_for_open_conversations():
    from assistant.analyzer import generate_conversation_summary  # LOCAL IMPORT AVOIDS CIRCULAR IMPORT
    conversations = Conversation.objects.filter(summary_data__isnull=True)
    logger.info(f"[CELERY BEAT] Found {conversations.count()} conversations to process.")
    print(f"[CELERY BEAT] Found {conversations.count()} conversations to process.")

    for conv in conversations:
        logger.info(f"[CELERY BEAT] Processing conversation {conv.session_id}")
        print(f"[CELERY BEAT] Processing conversation {conv.session_id}")
        summary_data = generate_conversation_summary(conv.session_id)
        if summary_data and summary_data != {"status": "error", "message": "No messages"}:
            summary_text = json.dumps(summary_data, indent=2, ensure_ascii=False)
            send_conversation_summary.apply_async(args=[summary_text], countdown=3)