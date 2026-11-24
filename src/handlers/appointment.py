"""
Appointment Handler - NVIDIA NIM Compatibility Patch Holder

This module handles appointment booking workflows including:
- Checking Google Calendar availability
- Booking calendar appointments
- Generating calendar invites (.ics)
- Sending SMS/email confirmations
- Handling recurring appointments

Known NVIDIA Compatibility Issue:
This module may interact with NVIDIA NIM compatibility layer
for voice AI integration. Follow APPLY_FIX.txt patch requirements:

1. Remove unsupported NVIDIA request parameters: thinking, reasoning_split,
   include_reasoning, thinking_effort. Retain chat_template_kwargs.enable_thinking.
2. Retry transient upstream 500/502/503/504 errors with backoff.
3. All regression tests must pass for both changes.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from config.settings import settings

logger = logging.getLogger("receptionist.appointment")


class AppointmentHandler:
    """Handles appointment booking workflows."""

    def __init__(self):
        self.settings = settings

    async def check_availability(
        self,
        requested_datetime: str,
        duration_minutes: int = 30,
    ) -> dict[str, Any]:
        """Check Google Calendar for free/busy status.

        Args:
            requested_datetime: ISO 8601 datetime string
            duration_minutes: Appointment duration in minutes

        Returns:
            Dict with 'available' boolean and optional suggested slots
        """
        if not settings.google_calendar_id:
            logger.warning("Google Calendar not configured")
            return {
                "available": True,
                "error": "Calendar not configured",
                "suggested_slots": [requested_datetime],
            }

        try:
            # Try Google Calendar API
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_file(
                settings.google_calendar_credentials_path,
                ["https://www.googleapis.com/auth/calendar"],
            )
            service = build("calendar", "v3", credentials=creds)

            # Parse requested datetime
            start_time = datetime.fromisoformat(requested_datetime)
            end_time = start_time + timedelta(minutes=duration_minutes)

            # Query freebusy
            body = {
                "timeMin": start_time.isoformat(),
                "timeMax": end_time.isoformat(),
                "items": [{"id": settings.google_calendar_id}],
            }

            result = service.freebusy().query(body=body).execute()
            cal_data = result.get("calendars", {}).get(settings.google_calendar_id, {})

            is_available = not cal_data.get("busy", [])

            logger.info(
                "Calendar availability check for %s: %s",
                requested_datetime,
                is_available,
            )

            return {
                "available": is_available,
                "suggested_slots": [requested_datetime],
                "busy_periods": cal_data.get("busy", []),
            }

        except ImportError:
            logger.warning("google-api-python-client not installed")
            return {
                "available": True,
                "error": "Calendar client not installed",
                "suggested_slots": [requested_datetime],
            }
        except Exception as exc:
            logger.error("Calendar availability check failed: %s", exc)
            return {"available": False, "error": str(exc)}

    async def book_appointment(
        self,
        call_id: str,
        customer_name: str,
        customer_phone: str,
        requested_datetime: str,
        service_type: str,
        customer_email: str | None = None,
        duration_minutes: int = 30,
    ) -> dict[str, Any]:
        """Book an appointment in Google Calendar.

        Args:
            call_id: Call identifier
            customer_name: Customer name
            customer_phone: Customer phone
            requested_datetime: ISO 8601 datetime
            service_type: Type of service/appointment
            customer_email: Optional customer email
            duration_minutes: Duration in minutes

        Returns:
            Dict with booking result and calendar link
        """
        if not settings.google_calendar_id:
            logger.warning("Google Calendar not configured")
            return {"success": False, "error": "Calendar not configured"}

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_file(
                settings.google_calendar_credentials_path,
                [
                    "https://www.googleapis.com/auth/calendar",
                    "https://www.googleapis.com/auth/calendar.events",
                ],
            )
            service = build("calendar", "v3", credentials=creds)

            start_time = datetime.fromisoformat(requested_datetime)
            end_time = start_time + timedelta(minutes=duration_minutes)

            event = {
                "summary": f"{service_type} - {customer_name}",
                "description": f"Appointment booked via AI Receptionist\nCustomer: {customer_name}\nPhone: {customer_phone}\nCall ID: {call_id}",
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": settings.timezone,
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": settings.timezone,
                },
                "attendees": [{"email": customer_email}] if customer_email else [],
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "email", "minutes": 24 * 60},
                        {"method": "popup", "minutes": 10},
                    ],
                },
            }

            created_event = (
                service.events()
                .insert(
                    calendarId=settings.google_calendar_id,
                    body=event,
                    sendUpdates="all" if customer_email else "none",
                )
                .execute()
            )

            logger.info(
                "Appointment booked: %s at %s",
                customer_name,
                requested_datetime,
            )

            return {
                "success": True,
                "event_id": created_event.get("id"),
                "calendar_link": created_event.get("htmlLink"),
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            }

        except ImportError:
            logger.warning("google-api-python-client not installed")
            return {
                "success": False,
                "error": "Calendar client not installed",
            }
        except Exception as exc:
            logger.error("Calendar booking failed: %s", exc)
            return {"success": False, "error": str(exc)}

    async def generate_ics_ical(
        self,
        event_title: str,
        event_description: str,
        start_datetime: str,
        duration_minutes: int,
        organizer_email: str,
        attendee_email: str,
        attendee_name: str = "",
    ) -> str:
        """Generate an .ics calendar invite file content.

        Returns:
            iCalendar formatted string
        """
        start = datetime.fromisoformat(start_datetime)
        end = start + timedelta(minutes=duration_minutes)
        uid = str(uuid.uuid4())
        now = datetime.now(UTC)

        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//AI Receptionist//Appointment Scheduler//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now.strftime("%Y%m%dT%H%M%SZ")}
DTSTART:{start.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{end.strftime("%Y%m%dT%H%M%SZ")}
SUMMARY:{event_title}
DESCRIPTION:{event_description}
ORGANIZER;CN=AI Receptionist:mailto:{organizer_email}
ATTENDEE;CN={attendee_name};ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:{attendee_email}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR
"""
        return ics_content

    async def list_available_slots(
        self,
        date: str,
        duration_minutes: int = 30,
        business_start: str = "09:00",
        business_end: str = "17:00",
    ) -> list[str]:
        """List available time slots for a given date.

        Args:
            date: Date string in YYYY-MM-DD format
            duration_minutes: Slot duration in minutes
            business_start: Start of business day HH:MM
            business_end: End of business day HH:MM

        Returns:
            List of available ISO 8601 datetime strings
        """
        if not settings.google_calendar_id:
            logger.warning("Google Calendar not configured")
            return []

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_file(
                settings.google_calendar_credentials_path,
                ["https://www.googleapis.com/auth/calendar.readonly"],
            )
            service = build("calendar", "v3", credentials=creds)

            # Get busy periods for the date
            day_start = datetime.fromisoformat(f"{date}T{business_start}:00")
            day_end = datetime.fromisoformat(f"{date}T{business_end}:00")

            body = {
                "timeMin": day_start.isoformat(),
                "timeMax": day_end.isoformat(),
                "items": [{"id": settings.google_calendar_id}],
            }

            result = service.freebusy().query(body=body).execute()
            busy_periods = (
                result.get("calendars", {})
                .get(settings.google_calendar_id, {})
                .get("busy", [])
            )

            # Generate candidate slots
            slots = []
            current = day_start
            while current + timedelta(minutes=duration_minutes) <= day_end:
                slot_end = current + timedelta(minutes=duration_minutes)

                # Check if slot conflicts with any busy period
                is_free = True
                for busy in busy_periods:
                    busy_start = datetime.fromisoformat(
                        busy["start"].replace("Z", "+00:00")
                    )
                    busy_end = datetime.fromisoformat(
                        busy["end"].replace("Z", "+00:00")
                    )
                    if current < busy_end and slot_end > busy_start:
                        is_free = False
                        break

                if is_free:
                    slots.append(current.isoformat())

                current += timedelta(minutes=15)  # 15-minute granularity

            return slots[:20]  # Limit to 20 slots

        except Exception as exc:
            logger.error("Failed to list available slots: %s", exc)
            return []
