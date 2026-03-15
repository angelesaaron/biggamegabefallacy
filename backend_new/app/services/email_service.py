import resend
from app.config import settings


class EmailService:
    def __init__(self):
        resend.api_key = settings.RESEND_API_KEY

    async def send_password_reset(self, to_email: str, reset_url: str) -> None:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": to_email,
            "subject": "Reset your Big Game Gabe password",
            "html": self._reset_template(reset_url),
        })

    async def send_email_verification(self, to_email: str, verify_url: str) -> None:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": to_email,
            "subject": "Confirm your new email — Big Game Gabe",
            "html": self._verify_email_template(verify_url),
        })

    def _reset_template(self, url: str) -> str:
        return f"""
        <p>You requested a password reset for your Big Game Gabe account.</p>
        <p><a href="{url}">Reset your password</a></p>
        <p>This link expires in 1 hour. If you didn't request this, ignore this email.</p>
        """

    def _verify_email_template(self, url: str) -> str:
        return f"""
        <p>Confirm your new email address for Big Game Gabe.</p>
        <p><a href="{url}">Confirm email change</a></p>
        <p>This link expires in 24 hours. If you didn't request this, ignore this email.</p>
        """


email_service = EmailService()
