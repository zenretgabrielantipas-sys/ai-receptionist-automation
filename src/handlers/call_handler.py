"""
Unified Call Handler for AI Receptionist.

Orchestrates voice provider interactions, call recording, transcription,
intent routing, and graceful error handling with automatic failover.
"""

import logging
from datetime import UTC, datetime

from database import CallRecord
from handlers.audio_transcriber import AudioTranscriber

from providers.voice import VoiceProviderFactory, voice_failover

logger = logging.getLogger("providers.voice.call_handler")


class CallHandler:
    """Unified call handler for AI receptionist voice interactions."""

    def __init__(self):
        self.voice_provider = VoiceProviderFactory.get_primary_provider()
        self.failover = voice_failover
        self.active_calls: dict[str, dict] = {}
        self.transcriber = AudioTranscriber()

    async def handle_call_start(
        self, call_id: str, caller_number: str, callee_number: str
    ) -> dict:
        """Handle an incoming call start event."""
        logger.info(f"Call started: {call_id} from {caller_number}")

        # Initialize call state
        self.active_calls[call_id] = {
            "call_id": call_id,
            "caller_number": caller_number,
            "callee_number": callee_number,
            "started_at": datetime.now(UTC).isoformat(),
            "status": "active",
            "intent": None,
            "transcript_segments": [],
            "reasoning_content": [],
        }

        # Store call record in database
        CallRecord.create(
            call_id=call_id,
            caller_number=caller_number,
            callee_number=callee_number,
            started_at=self.active_calls[call_id]["started_at"],
        )

        # Get voice response from provider
        try:
            response = await self.failover.handle_call_start(
                call_id, caller_number, callee_number
            )
        except Exception as exc:
            logger.error(f"Voice provider failed on call start: {exc}")
            response = None

        # Build TTS response
        response_text = (
            response.text
            if response and response.text
            else "Hello, thank you for calling. How can I help you today?"
        )

        return {
            "call_id": call_id,
            "action": "speak",
            "text": response_text,
            "listen": True,
        }

    async def handle_speech(
        self, call_id: str, transcript: str, is_final: bool
    ) -> dict:
        """Handle transcribed speech from the caller."""
        call_info = self.active_calls.get(call_id)
        if not call_info:
            logger.warning(f"Speech received for unknown call: {call_id}")
            return {"action": "error", "text": "Call session not found"}

        # Store transcript segment
        call_info["transcript_segments"].append(
            {
                "text": transcript,
                "is_final": is_final,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        # Only process final transcript segments
        if not is_final:
            return {"action": "listen"}

        logger.info(f"Speech final: call_id={call_id}, transcript={transcript[:100]}...")

        try:
            response = await self.failover.handle_speech(call_id, transcript, is_final)
        except Exception as exc:
            logger.error(f"Voice provider failed on speech: {exc}")
            response = None

        if response and response.end_call:
            await self._finalize_call(call_id, "completed_by_user")
            return {
                "action": "speak",
                "text": response.text or "Thank you for calling. Goodbye!",
                "listen": False,
                "end_call": True,
            }

        if response and response.function_call:
            return await self._handle_function_call(
                call_id, response.function_call
            )

        return {
            "action": "speak",
            "text": response.text or "I'm sorry, I didn't understand that.",
            "listen": True,
        }

    async def handle_function_call(
        self, call_id: str, function_name: str, parameters: dict
    ) -> dict:
        """Handle a function call request from the voice agent."""
        call_info = self.active_calls.get(call_id)
        if not call_info:
            return {"action": "error", "text": "Call session not found"}

        logger.info(
            f"Function call: {function_name} for call {call_id}"
        )

        try:
            await self.failover.handle_function_call(
                call_id, function_name, parameters
            )
        except Exception as exc:
            logger.error(f"Voice provider failed on function call: {exc}")
            return {
                "action": "speak",
                "text": "I'm sorry, I encountered an error processing your request.",
                "listen": True,
            }

        # Dispatch to appropriate handler
        if function_name == "handle_appointment":
            return await self._handle_appointment_function(call_id, parameters)
        elif function_name == "handle_faq":
            return await self._handle_faq_function(call_id, parameters)
        elif function_name == "handle_lead_intake":
            return await self._handle_lead_intake_function(call_id, parameters)
        else:
            return {
                "action": "speak",
                "text": f"I'm not sure how to handle {function_name}.",
                "listen": True,
            }

    async def handle_call_end(
        self, call_id: str, duration: int, reason: str
    ) -> None:
        """Handle call termination."""
        call_info = self.active_calls.get(call_id)
        if call_info:
            call_info["status"] = "completed"
            call_info["ended_at"] = datetime.now(UTC).isoformat()
            call_info["duration"] = duration
            call_info["outcome"] = reason

        await self.failover.handle_call_end(call_id, duration, reason)

        # Save call record
        CallRecord.update(call_id, **{
            "ended_at": call_info.get("ended_at") if call_info else None,
            "status": "completed",
            "outcome": reason,
        })

        logger.info(f"Call ended: {call_id}, duration: {duration}s, reason: {reason}")

    async def get_call_transcript(
        self, call_id: str
    ) -> list:
        """Get full call transcript including voice provider data."""
        call_info = self.active_calls.get(call_id)
        if not call_info:
            return []

        # Try provider transcript first
        try:
            provider_transcript = await self.failover.get_transcript(call_id)
            if provider_transcript:
                return provider_transcript
        except Exception as exc:
            logger.error(f"Provider transcript fetch failed: {exc}")

        # Fall back to local transcript segments
        return call_info.get("transcript_segments", [])

    async def get_call_recording_url(
        self, call_id: str
    ) -> str | None:
        """Get recording URL for a completed call."""
        try:
            return await self.failover.get_recording_url(call_id)
        except Exception as exc:
            logger.error(f"Recording URL fetch failed: {exc}")
            return None

    async def webhook_handler(self, payload: dict):
        """Process incoming webhook from voice provider."""
        event_type = payload.get("event", "")
        call_id = payload.get("call_id", "")

        logger.info(f"Voice webhook: {event_type} for call {call_id}")

        if event_type == "call_start":
            return await self.handle_call_start(
                call_id,
                payload.get("caller_number", "unknown"),
                payload.get("callee_number", ""),
            )

        elif event_type == "speech":
            return await self.handle_speech(
                call_id,
                payload.get("transcript", ""),
                payload.get("is_final", False),
            )

        elif event_type == "function_call":
            return await self.handle_function_call(
                call_id,
                payload.get("function_name", ""),
                payload.get("parameters", {}),
            )

        elif event_type == "call_end":
            await self.handle_call_end(
                call_id,
                payload.get("duration_seconds", 0),
                payload.get("reason", "completed"),
            )
            return {"action": "call_ended"}

        return {"action": "ignored", "event": event_type}

    # ── Internal handlers ──

    async def _handle_appointment_function(
        self, call_id: str, parameters: dict
    ) -> dict:
        """Delegate appointment function to appointment handler."""
        from handlers.appointment import AppointmentHandler

        handler = AppointmentHandler()
        return await handler.handle_appointment_request(call_id, parameters)

    async def _handle_faq_function(
        self, call_id: str, parameters: dict
    ) -> dict:
        """Delegate FAQ question to FAQ handler."""
        from handlers.faq import FAQHandler

        handler = FAQHandler()
        question = parameters.get("question", "")
        result = await handler.answer_question(question)

        return {
            "action": "speak",
            "text": result.get("answer", "I'm not sure about that."),
            "listen": True,
        }

    async def _handle_lead_intake_function(
        self, call_id: str, parameters: dict
    ) -> dict:
        """Delegate lead intake to lead handler."""
        from handlers.lead_intake import LeadIntakeHandler

        handler = LeadIntakeHandler()
        return await handler.capture_lead(
            call_id=call_id,
            name=parameters.get("name", ""),
            phone=parameters.get("phone", ""),
            email=parameters.get("email"),
            company=parameters.get("company"),
            notes=parameters.get("notes"),
            urgency=parameters.get("urgency", "normal"),
        )

    async def _handle_general_intent(
        self, call_id: str, intent: str, entities: dict
    ) -> dict:
        """Handle general unrecognized intent."""
        return {
            "action": "speak",
            "text": "I'm sorry, I didn't understand that. Could you please rephrase?",
            "listen": True,
            "transfer_to_human": True,
        }

    async def _finalize_call(self, call_id: str, reason: str) -> None:
        """Finalize a call and clean up state."""
        await self.handle_call_end(call_id, 0, reason)
        self.active_calls.pop(call_id, None)


# Singleton instance
call_handler = CallHandler()
