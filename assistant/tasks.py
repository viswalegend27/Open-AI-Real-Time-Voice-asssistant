import os
from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings

@shared_task
def send_conversation_summary(summary_text):
    # Prepare file path
    file_path = os.path.join(settings.BASE_DIR, 'conversation_summary.txt')
    # Write the summary to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)

    # Get recipient email from .env
    recipient = os.environ.get('MAIN_EMAIL')
    if not recipient:
        raise Exception("MAIN_EMAIL environment variable is not set.")

    # Create and send the email with the file as attachment
    email = EmailMessage(
        'Your Conversation Summary',
        'Attached is your conversation summary as a text file.',
        settings.EMAIL_HOST_USER,
        [recipient],
    )
    email.attach_file(file_path)
    email.send()

    # Optionally, remove the file after sending
    os.remove(file_path)