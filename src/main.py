"""
AI Receptionist Automation - Main Webhook Server

Receives webhooks from:
- VAPI / Retell AI voice platform
- Twilio (SMS status, voice events)
- Google Calendar (push notifications)
- Slack (slash commands)

Orchestrates the full receptionist workflow:
Call -> Screen -> Intent -> Route -> Fulfill -> Notify -> Report
"""

import asyncio
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

# Add src/ and parent directory to sys.path for imports
_src_dir = os.path.dirname(os.path.abspath(__file__))
_sys_dir = os.path.dirname(_src_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
if _sys_dir not in sys.path:
    sys.path.insert(0, _sys_dir)

from analytics import AnalyticsHandler  # noqa: E402
from database import (  # noqa: E402
    CallRecord,
    init_db,
)
from fastapi import (  # noqa: E402
    FastAPI,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse, PlainTextResponse  # noqa: E402
from handlers import (  # noqa: E402
    AppointmentHandler,
    FAQHandler,
    LeadIntakeHandler,
    NotificationHandler,
)
from pydantic import BaseModel  # noqa: E402
from web_dashboard import router as dashboard_router  # noqa: E402

from config.settings import settings  # noqa: E402

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
if settings.log_file:
    file_handler = logging.FileHandler(settings.log_file)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(file_handler)
logger = logging.getLogger("receptionist")

app = FastAPI(title="AI Receptionist Automation", version="1.0.0")

# ── Initialize singleton handlers ──
appointment_handler = AppointmentHandler()
faq_handler = FAQHandler()
lead_intake_handler = LeadIntakeHandler()
notification_handler = NotificationHandler()
analytics_handler = AnalyticsHandler()


# ── In-memory call state (use database in production) ──
call_state: dict[str, dict] = {}


# ── Data Models ──
class CallStartEvent(BaseModel):
    call_id: str
    caller_number: str
    callee_number: str
    timestamp: str
    direction: str  # "inbound" or "outbound"


class IntentRoutingRequest(BaseModel):
    call_id: str
    intent: str  # "appointment", "faq", "lead", "other"
    confidence: float
    entities: dict[str, Any] = {}


class AppointmentRequest(BaseModel):
    call_id: str
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    requested_datetime: str  # ISO 8601
    service_type: str
    duration_minutes: int = 30


class LeadIntakeRequest(BaseModel):
    call_id: str
    name: str
    phone: str
    email: str | None = None
    company: str | None = None
    notes: str | None = None
    urgency: str = "normal"  # low, normal, high, urgent


class WebhookEvent(BaseModel):
    event: str
    data: dict


# ── Voice Agent Handlers (VAPI / Retell) ──


async def handle_vapi_call_start(payload: dict) -> dict:
    """Handle incoming call webhook from VAPI."""
    call_id = payload.get("call_id", str(uuid.uuid4()))
    caller_number = payload.get("from", "unknown")
    callee_number = payload.get("to", settings.twilio_phone_number)

    # Persist call record
    CallRecord.create(
        call_id=call_id,
        caller_number=caller_number,
        callee_number=callee_number,
        started_at=datetime.now(UTC).isoformat(),
    )

    call_state[call_id] = {
        "call_id": call_id,
        "caller_number": caller_number,
        "callee_number": callee_number,
        "started_at": datetime.now(UTC).isoformat(),
        "status": "active",
        "intent": None,
        "outcome": None,
    }

    logger.info("Call started: %s from %s", call_id, caller_number)

    # Return instructions to VAPI for the greeting
    return {
        "type": "tts",
        "text": "Hello, thank you for calling. How can I help you today?",
        "listen": True,
        "timeout": 10,
    }


async def handle_vapi_intent(payload: dict) -> dict:
    """Handle intent detection from VAPI."""
    call_id = payload.get("call_id")
    intent = payload.get("intent", "other")
    confidence = payload.get("confidence", 0.0)
    entities = payload.get("entities", {})

    if call_id and call_id in call_state:
        call_state[call_id]["intent"] = intent
        call_state[call_id]["confidence"] = confidence

    logger.info(
        "Intent detected: %s (confidence: %s) for call %s", intent, confidence, call_id
    )

    # Route based on intent using orchestrator
    routing_result = await orchestrator.route_call(
        event=IntentRoutingRequest(
            call_id=call_id or "",
            intent=intent,
            confidence=confidence,
            entities=entities,
        )
    )

    return routing_result


# ── Calendar Integration ──


async def check_availability(
    requested_datetime: str, duration_minutes: int = 30
) -> dict:
    """Check Google Calendar for free/busy status."""
    return await appointment_handler.check_availability(
        requested_datetime=requested_datetime,
        duration_minutes=duration_minutes,
    )


async def book_appointment(event_details: dict) -> dict:
    """Book an appointment in Google Calendar."""
    return await appointment_handler.book_appointment(
        call_id=event_details.get("call_id", ""),
        customer_name=event_details.get("customer_name", ""),
        customer_phone=event_details.get("customer_phone", ""),
        requested_datetime=event_details.get("requested_datetime", ""),
        service_type=event_details.get("service_type", "general"),
        customer_email=event_details.get("customer_email"),
        duration_minutes=event_details.get("duration_minutes", 30),
    )


# ── CRM Integration ──


async def save_lead(lead: LeadIntakeRequest) -> dict:
    """Save lead to Airtable (or HubSpot)."""
    return await lead_intake_handler.capture_lead(
        call_id=lead.call_id,
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        company=lead.company,
        notes=lead.notes,
        urgency=lead.urgency,
    )


async def save_call_record(call_data: dict) -> dict:
    """Save call record to Airtable calls table."""
    if not settings.airtable_api_key or not settings.airtable_table_calls:
        return {"saved": False, "error": "CRM not configured"}

    try:
        import httpx

        url = (
            f"https://api.airtable.com/v0/"
            f"{settings.airtable_base_id}/{settings.airtable_table_calls}"
        )
        headers = {
            "Authorization": f"Bearer {settings.airtable_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json={"fields": call_data},
                timeout=10,
            )
            response.raise_for_status()
            return {"saved": True, "record_id": response.json().get("id")}

    except Exception as exc:
        logger.error("Call record save failed: %s", exc)
        return {"saved": False, "error": str(exc)}


# ── Notifications ──


async def send_sms(to_number: str, message: str) -> dict:
    """Send SMS via Twilio."""
    return await notification_handler.send_sms(to_number=to_number, message=message)


async def send_email(to_email: str, subject: str, body: str) -> dict:
    """Send email via SendGrid or Resend."""
    return await notification_handler.send_email(
        to_email=to_email, subject=subject, body_html=body
    )


async def send_slack_alert(message: str, channel: str | None = None) -> dict:
    """Send alert to Slack via webhook."""
    return await notification_handler.send_slack_alert(message=message, channel=channel)


# ── Analytics ──


async def log_call_analytics(call_data: dict) -> dict:
    """Log call data to Mixpanel and/or Google Sheets."""
    return await analytics_handler.track_call_event(event=call_data)


# ── Workflow Orchestrator ──


class ReceptionistOrchestrator:
    """Orchestrates the full receptionist workflow."""

    def __init__(self):
        self.settings = settings
        self.appointment_handler = appointment_handler
        self.faq_handler = faq_handler
        self.lead_intake_handler = lead_intake_handler
        self.notification_handler = notification_handler
        self.analytics_handler = analytics_handler

    async def route_call(self, event: IntentRoutingRequest) -> dict:
        """Route call based on detected intent."""
        call_id = event.call_id

        if event.intent == "appointment":
            return await self._handle_appointment_flow(call_id, event.entities)
        elif event.intent == "faq":
            return await self._handle_faq_flow(call_id, event.entities)
        elif event.intent == "lead":
            return await self._handle_lead_intake_flow(call_id, event.entities)
        else:
            return await self._handle_general_flow(call_id, event.entities)

    async def _handle_appointment_flow(self, call_id: str, entities: dict) -> dict:
        """Handle appointment booking flow."""
        steps = []

        # Step 1: Check availability
        requested_time = entities.get("requested_datetime", "")
        duration = entities.get("duration_minutes", 30)

        availability = await self.appointment_handler.check_availability(
            requested_datetime=requested_time,
            duration_minutes=duration,
        )
        steps.append({"step": "check_availability", "result": availability})

        if not availability.get("available", False):
            return {
                "success": False,
                "steps": steps,
                "tts": "I'm sorry, that time slot is not available. Would you like a different time?",
            }

        # Step 2: Book appointment
        booking = await self.appointment_handler.book_appointment(
            call_id=call_id,
            customer_name=entities.get("customer_name", ""),
            customer_phone=entities.get("customer_phone", ""),
            requested_datetime=requested_time,
            service_type=entities.get("service_type", "general"),
            customer_email=entities.get("customer_email"),
            duration_minutes=duration,
        )
        steps.append({"step": "book_appointment", "result": booking})

        # Step 3: Send confirmation
        if booking.get("success"):
            customer_phone = entities.get("customer_phone", "")
            customer_email = entities.get("customer_email", "")

            if customer_phone:
                await self.notification_handler.send_sms(
                    to_number=customer_phone,
                    message=(
                        f"Your appointment is confirmed for {requested_time}. "
                        f"Thank you!"
                    ),
                )
            if customer_email:
                await self.notification_handler.send_email(
                    to_email=customer_email,
                    subject="Appointment Confirmation",
                    body=f"<p>Your appointment is confirmed for <strong>{requested_time}</strong>.</p>",
                )

            steps.append({"step": "send_confirmation", "result": {"sent": True}})

            # Step 4: Slack alert
            await self.notification_handler.send_slack_alert(
                message=(
                    f"\U0001f4c5 New appointment booked: "
                    f"{entities.get('customer_name')} at {requested_time}"
                )
            )

        return {
            "success": booking.get("success", False),
            "steps": steps,
            "tts": "Your appointment has been booked. You'll receive a confirmation shortly.",
            "calendar_link": booking.get("calendar_link"),
        }

    async def _handle_faq_flow(self, call_id: str, entities: dict) -> dict:
        """Handle FAQ flow - return knowledge base answer."""
        question = entities.get("question", "")

        result = await self.faq_handler.answer_question(question=question)

        return {
            "success": True,
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence", 0.0),
            "source": result.get("source", "fallback"),
            "tts": result.get("answer", "I'm sorry, I didn't understand that."),
        }

    async def _handle_lead_intake_flow(self, call_id: str, entities: dict) -> dict:
        """Handle lead intake flow."""
        lead = LeadIntakeRequest(
            call_id=call_id,
            name=entities.get("name", ""),
            phone=entities.get("phone", ""),
            email=entities.get("email"),
            company=entities.get("company"),
            notes=entities.get("notes"),
            urgency=entities.get("urgency", "normal"),
        )

        # Save to CRM
        crm_result = await self.lead_intake_handler.capture_lead(
            call_id=lead.call_id,
            name=lead.name,
            phone=lead.phone,
            email=lead.email,
            company=lead.company,
            notes=lead.notes,
            urgency=lead.urgency,
        )

        # Slack alert for urgent leads
        if lead.urgency in ("high", "urgent"):
            await self.notification_handler.send_slack_alert(
                message=(
                    f"\U0001f6a8 Urgent lead: {lead.name} ({lead.phone}) "
                    f"- {lead.urgency} priority"
                )
            )

        return {
            "success": crm_result.get("saved", False),
            "record_id": crm_result.get("record_id"),
            "lead_score": crm_result.get("lead_score"),
            "urgency": lead.urgency,
            "tts": "Thank you. I've recorded your information and our team will follow up shortly.",
        }

    async def _handle_general_flow(self, call_id: str, entities: dict) -> dict:
        """Handle general/unrecognized intent."""
        return {
            "success": False,
            "tts": "I'm sorry, I didn't understand that. Could you please rephrase?",
            "transfer_to_human": True,
        }

    async def finalize_call(self, call_id: str, outcome: str) -> dict:
        """Finalize call - save records, send analytics."""
        call_info = call_state.get(call_id, {})
        call_info["outcome"] = outcome
        call_info["ended_at"] = datetime.now(UTC).isoformat()

        # Save call record to database
        CallRecord.update(
            call_id,
            **{
                "ended_at": call_info["ended_at"],
                "status": "completed",
                "outcome": outcome,
            },
        )

        # Log analytics
        await self.analytics_handler.track_call_event(
            event={
                "call_id": call_id,
                "event_name": "call_completed",
                "outcome": outcome,
                "intent": call_info.get("intent"),
                "duration_seconds": (
                    datetime.fromisoformat(call_info.get("ended_at", "1970-01-01"))
                    - datetime.fromisoformat(call_info.get("started_at", "1970-01-01"))
                ).total_seconds()
                if call_info.get("ended_at") and call_info.get("started_at")
                else 0,
            }
        )

        logger.info("Call finalized: %s - %s", call_id, outcome)
        return {"call_id": call_id, "outcome": outcome, "status": "completed"}


orchestrator = ReceptionistOrchestrator()


# ── FastAPI Routes ──


@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {
        "service": "AI Receptionist Automation",
        "status": "healthy",
        "version": "1.0.0",
        "settings": settings.to_dict(),
    }


@app.get("/health")
async def health():
    """Simple health check."""
    return {"status": "ok"}


@app.post("/webhooks/vapi/call-start")
async def vapi_call_start(event: CallStartEvent):
    """VAPI: Incoming call started."""
    result = await handle_vapi_call_start(event.dict())
    return JSONResponse(result)


@app.post("/webhooks/vapi/intent")
async def vapi_intent(event: IntentRoutingRequest):
    """VAPI: Intent detected - route accordingly."""
    routing = await handle_vapi_intent(event.dict())

    # Execute orchestration
    result = await orchestrator.route_call(event)
    routing["orchestration"] = result

    return JSONResponse(routing)


@app.post("/webhooks/vapi/call-end")
async def vapi_call_end(event: WebhookEvent):
    """VAPI: Call ended - finalize records."""
    call_id = event.data.get("call_id")
    outcome = event.data.get("outcome", "completed")

    if call_id:
        result = await orchestrator.finalize_call(call_id, outcome)
        return JSONResponse(result)

    return JSONResponse({"status": "no_call_id"})


@app.post("/webhooks/vapi/function-call")
async def vapi_function_call(payload: dict):
    """VAPI: Function call from voice agent (e.g., book appointment)."""
    function_name = payload.get("function_name")
    parameters = payload.get("parameters", {})
    call_id = payload.get("call_id")

    if function_name == "book_appointment":
        AppointmentRequest(call_id=call_id, **parameters)
        result = await orchestrator._handle_appointment_flow(call_id, parameters)
        return JSONResponse(result)
    elif function_name == "save_lead":
        LeadIntakeRequest(call_id=call_id, **parameters)
        result = await orchestrator._handle_lead_intake_flow(call_id, parameters)
        return JSONResponse(result)
    elif function_name == "check_availability":
        result = await check_availability(
            parameters.get("datetime", ""),
            parameters.get("duration_minutes", 30),
        )
        return JSONResponse(result)

    return JSONResponse(
        {"error": f"Unknown function: {function_name}"}, status_code=400
    )


@app.post("/webhooks/twilio/sms-status")
async def twilio_sms_status(event: WebhookEvent):
    """Twilio: SMS delivery status webhook."""
    logger.info("SMS status update: %s", event.data)
    return JSONResponse({"received": True})


@app.post("/webhooks/slack/command")
async def slack_command(request: Request):
    """Slack: Slash command handler."""
    form = await request.form()
    command = form.get("command", "")
    form.get("text", "")

    if command == "/reception-stats":
        total_calls = len(call_state)
        active_calls = sum(
            1 for c in call_state.values() if c.get("status") == "active"
        )
        return PlainTextResponse(
            "*Receptionist Stats*\n"
            f"• Active calls: {active_calls}\n"
            f"• Total calls: {total_calls}\n"
            f"• Provider: {settings.voice_provider}"
        )

    return PlainTextResponse("Unknown command")


@app.websocket("/ws/calls")
async def websocket_calls(websocket: WebSocket):
    """WebSocket for real-time call monitoring."""
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(
                {
                    "calls": call_state,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass


# ── Mount dashboard router ──
app.include_router(dashboard_router)


if __name__ == "__main__":
    import uvicorn

    # Initialize database on startup
    init_db()

    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
