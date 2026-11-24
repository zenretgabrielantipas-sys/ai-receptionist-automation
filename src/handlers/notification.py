"""
Notification Handler

Handles SMS (Twilio), Email (SendGrid/Resend), and Slack notifications
for the AI Receptionist system.
"""

import logging
from typing import Any

import httpx

from config.settings import settings

logger = logging.getLogger("receptionist.notification")


class NotificationHandler:
    """Handles all notification channels for the receptionist."""

    def __init__(self):
        self.settings = settings

    async def send_sms(
        self, to_number: str, message: str, media_url: str | None = None
    ) -> dict[str, Any]:
        """Send SMS via Twilio.

        Args:
            to_number: Recipient phone number
            message: SMS message text
            media_url: Optional media URL to attach

        Returns:
            Dict with send result
        """
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            logger.warning("Twilio not configured")
            return {"sent": False, "error": "Twilio not configured"}

        try:
            from twilio.rest import Client

            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

            create_params = {
                "body": message,
                "from_": settings.twilio_phone_number,
                "to": to_number,
            }
            if media_url:
                create_params["media_url"] = [media_url]

            message_obj = client.messages.create(**create_params)
            logger.info("SMS sent to %s: %s", to_number, message_obj.sid)
            return {"sent": True, "sid": message_obj.sid}

        except Exception as exc:
            logger.error("SMS send failed: %s", exc)
            return {"sent": False, "error": str(exc)}

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send email via SendGrid or Resend.

        Args:
            to_email: Recipient email
            subject: Email subject
            body_html: HTML body content
            body_text: Optional plain text body
            attachments: Optional list of attachment dicts

        Returns:
            Dict with send result
        """
        # Try SendGrid first
        if settings.sendgrid_api_key:
            try:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Attachment, FileContent, Mail

                message = Mail(
                    from_email=settings.sendgrid_from_email,
                    to_emails=to_email,
                    subject=subject,
                    html_content=body_html,
                )
                if body_text:
                    message.plain_text_content = body_text

                if attachments:
                    for att in attachments:
                        attachment = Attachment()
                        attachment.file_content = FileContent(att.get("content", ""))
                        attachment.file_name = att.get("filename", "attachment")
                        attachment.file_type = att.get(
                            "type", "application/octet-stream"
                        )
                        attachment.disposition = "attachment"
                        message.attachment = attachment

                sg = SendGridAPIClient(settings.sendgrid_api_key)
                response = sg.send(message)
                logger.info("Email sent via SendGrid: %s", response.status_code)
                return {"sent": True, "status": response.status_code}

            except Exception as exc:
                logger.error("SendGrid email failed: %s", exc)

        # Fallback to Resend
        if settings.resend_api_key:
            try:
                payload = {
                    "from": settings.sendgrid_from_email,
                    "to": [to_email],
                    "subject": subject,
                    "html": body_html,
                }
                if body_text:
                    payload["text"] = body_text

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.resend.com/emails",
                        headers={
                            "Authorization": f"Bearer {settings.resend_api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=10,
                    )
                    response.raise_for_status()
                    logger.info("Email sent via Resend: %s", response.status_code)
                    return {"sent": True, "status": response.status_code}

            except Exception as exc:
                logger.error("Resend email failed: %s", exc)

        logger.warning("No email provider configured")
        return {"sent": False, "error": "No email provider configured"}

    async def send_slack_alert(
        self,
        message: str,
        channel: str | None = None,
        blocks: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Send alert to Slack via webhook.

        Args:
            message: Alert message text
            channel: Optional channel override
            blocks: Optional Slack blocks for rich formatting

        Returns:
            Dict with send result
        """
        if not settings.slack_webhook_url:
            logger.warning("Slack not configured")
            return {"sent": False, "error": "Slack not configured"}

        try:
            payload: dict[str, Any] = {
                "text": message,
                "channel": channel or settings.slack_channel,
                "username": "AI Receptionist",
                "icon_emoji": ":robot_face:",
            }

            if blocks:
                payload["blocks"] = blocks

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.slack_webhook_url, json=payload, timeout=10
                )
                response.raise_for_status()
                logger.info("Slack alert sent")
                return {"sent": True}

        except Exception as exc:
            logger.error("Slack alert failed: %s", exc)
            return {"sent": False, "error": str(exc)}

    async def send_appointment_confirmation(
        self,
        customer_name: str,
        customer_phone: str,
        customer_email: str | None,
        appointment_datetime: str,
        service_type: str,
        calendar_link: str | None = None,
        ics_content: str | None = None,
    ) -> dict[str, Any]:
        """Send appointment confirmation via SMS and Email.

        Args:
            customer_name: Customer name
            customer_phone: Customer phone
            customer_email: Optional customer email
            appointment_datetime: ISO 8601 datetime
            service_type: Type of service
            calendar_link: Optional Google Calendar link
            ics_content: Optional .ics file content

        Returns:
            Dict with send results for SMS and Email
        """
        results = {}

        # SMS confirmation
        if settings.sms_notifications_enabled and customer_phone:
            sms_msg = (
                f"Hi {customer_name}! Your appointment is confirmed for "
                f"{appointment_datetime}. Service: {service_type}. "
                f"Thank you for using our service!"
            )
            if calendar_link:
                sms_msg += f" View: {calendar_link}"
            results["sms"] = await self.send_sms(customer_phone, sms_msg)

        # Email confirmation
        if settings.email_notifications_enabled and customer_email:
            html_body = f"""
            <html>
            <body>
                <h2>Appointment Confirmation</h2>
                <p>Hi {customer_name},</p>
                <p>Your appointment has been confirmed:</p>
                <ul>
                    <li><strong>Date/Time:</strong> {appointment_datetime}</li>
                    <li><strong>Service:</strong> {service_type}</li>
                </ul>
                <p>Thank you for choosing our service!</p>
            </body>
            </html>
            """
            results["email"] = await self.send_email(
                to_email=customer_email,
                subject=f"Appointment Confirmation - {appointment_datetime}",
                body_html=html_body,
                body_text=f"Hi {customer_name}, your appointment is confirmed for {appointment_datetime}. Service: {service_type}.",
                attachments=[
                    {
                        "filename": "appointment.ics",
                        "content": ics_content or "",
                        "type": "text/calendar",
                    }
                ]
                if ics_content
                else None,
            )

        return results

    async def send_owner_alert(
        self,
        message: str,
        urgent: bool = False,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """Send alert to business owner via Slack and/or SMS.

        Args:
            message: Alert message
            urgent: Whether this is an urgent alert
            channel: Optional Slack channel

        Returns:
            Dict with send results
        """
        results = {}

        # Slack alert
        if settings.slack_webhook_url:
            results["slack"] = await self.send_slack_alert(
                message=message,
                channel=channel or settings.slack_channel,
            )

        # SMS to owner (if configured)
        if urgent and settings.owner_sms_reminders:
            # Owner phone would come from config or env
            owner_phone = getattr(settings, "owner_phone", None)
            if owner_phone:
                results["sms"] = await self.send_sms(owner_phone, message)

        return results

    async def send_calendar_invite_email(
        self,
        to_email: str,
        customer_name: str,
        appointment_datetime: str,
        service_type: str,
        ics_content: str,
        calendar_link: str | None = None,
    ) -> dict[str, Any]:
        """Send calendar invite via email with .ics attachment.

        Args:
            to_email: Recipient email
            customer_name: Customer name
            appointment_datetime: ISO 8601 datetime
            service_type: Service type
            ics_content: iCalendar content
            calendar_link: Optional calendar link

        Returns:
            Dict with send result
        """
        html_body = f"""
        <html>
        <body>
            <h2>Calendar Invite - {service_type}</h2>
            <p>Hi {customer_name},</p>
            <p>Your appointment has been scheduled:</p>
            <ul>
                <li><strong>Date/Time:</strong> {appointment_datetime}</li>
                <li><strong>Service:</strong> {service_type}</li>
            </ul>
            <p>Please add this event to your calendar using the attached .ics file.</p>
            {'<p><a href="' + calendar_link + '">View in Google Calendar</a></p>' if calendar_link else ""}
            <p>Thank you for using our service!</p>
        </body>
        </html>
        """

        return await self.send_email(
            to_email=to_email,
            subject=f"Calendar Invite: {service_type} - {appointment_datetime}",
            body_html=html_body,
            body_text=f"Hi {customer_name}, your {service_type} appointment is scheduled for {appointment_datetime}. Please add the attached .ics file to your calendar.",
            attachments=[
                {
                    "filename": "appointment.ics",
                    "content": ics_content,
                    "type": "text/calendar",
                }
            ],
        )
