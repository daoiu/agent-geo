"""Notifications API: send test email."""
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.domain.exceptions import NotificationError
from app.domain.notification.email_sender import send_email

router = APIRouter(prefix="/notifications", tags=["notifications"])


class TestEmailRequest(BaseModel):
    to: EmailStr


@router.post("/test")
async def send_test_email(body: TestEmailRequest) -> dict:
    try:
        await send_email(
            to=body.to,
            subject="[GEO Agent] Test Email",
            body="This is a test email from GEO Agent. If you received this, SMTP is working correctly.",
        )
        return {"ok": True}
    except NotificationError as e:
        return {"ok": False, "error": str(e)}
