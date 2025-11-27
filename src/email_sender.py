"""Email sender using Resend API."""

from datetime import datetime, timezone

import resend

from src.config import Config
from src.email_builder import EmailContent


class EmailSender:
    """Sends emails via Resend API."""

    def __init__(self, config: Config):
        self.config = config
        resend.api_key = config.resend_api_key

    def send_digest(self, email_content: EmailContent) -> bool:
        """
        Send the digest email via Resend.
        
        Args:
            email_content: The email content to send.
            
        Returns:
            True on success, False on failure.
        """
        try:
            response = resend.Emails.send(
                {
                    "from": self.config.email_from,
                    "to": self.config.email_to,
                    "subject": email_content.subject,
                    "html": email_content.html_body,
                    "text": email_content.text_body,
                }
            )
            print(f"📬 Email sent successfully (ID: {response.get('id', 'unknown')})")
            return True
        except Exception as e:
            print(f"❌ Email send failed: {e}")
            return False

    def send_failure_notification(self, error: Exception) -> None:
        """
        Send a failure notification email.
        
        Args:
            error: The exception that caused the failure.
        """
        try:
            date_str = datetime.now(timezone.utc).strftime("%b %d")
            resend.Emails.send(
                {
                    "from": self.config.email_from,
                    "to": self.config.email_to,
                    "subject": f"❌ X Digest failed – {date_str}",
                    "text": f"""Your X digest failed to generate.

Error: {str(error)}

Error type: {type(error).__name__}

Please check the Railway logs for more details.

---
This is an automated message from your X Digest bot.
""",
                }
            )
            print("📬 Failure notification sent")
        except Exception as e:
            print(f"❌ Failed to send failure notification: {e}")

