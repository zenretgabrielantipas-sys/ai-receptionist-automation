"""
Retell AI Voice Provider Implementation.

Retell AI provides voice agent capabilities with realistic conversational AI,
function calling, and call analytics. Used as fallback when VAPI is unavailable.
"""

import logging

from config.settings import settings
from providers.voice.base import BaseVoiceProvider, VoiceResponse

logger = logging.getLogger("providers.retell")


class RetellProvider(BaseVoiceProvider):
    """Retell AI voice provider (fallback for NVIDIA NIM)."""

    def __init__(self, api_key: str, agent_id: str | None = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.agent_id = agent_id or settings.retell_agent_id
        self.base_url = "https://api.retellai.com"

    async def handle_call_start(
        self, call_id: str, caller_number: str, callee_number: str
    ) -> VoiceResponse:
        """Handle an incoming call start event via Retell."""
        logger.info(f"Retell call started: {call_id} from {caller_number}")

        return VoiceResponse(
            text="Hello, you've reached our AI receptionist. How can I assist you today?",
        )

    async def handle_speech(
        self, call_id: str, transcript: str, is_final: bool
    ) -> VoiceResponse:
        """Handle transcribed speech from the caller via Retell."""
        logger.debug(f"Retell speech: call_id={call_id}, transcript={transcript[:50]}..., final={is_final}")

        if not is_final:
            return VoiceResponse(text=None)

        # Retell intent detection
        try:
            response = await self._retell_request(
                "POST",
                "/v1/detect-intent",
                {
                    "call_id": call_id,
                    "transcript": transcript,
                    "agent_id": self.agent_id,
                },
            )

            intent = response.get("intent", "other")
            entities = response.get("entities", {})

            logger.info(f"Retell intent detected: {intent} (confidence: {response.get('confidence', 0.0)})")

            return VoiceResponse(
                text=f"I understand you want to {intent}. Let me help you with that.",
                function_call={"name": f"handle_{intent}", "arguments": entities},
            )

        except Exception as exc:
            logger.error(f"Retell intent detection failed: {exc}")
            return VoiceResponse(text="I'm sorry, I didn't catch that. Could you please repeat?")

    async def handle_function_call(
        self, call_id: str, function_name: str, parameters: dict
    ) -> VoiceResponse:
        """Handle a function call request from Retell AI."""
        logger.info(f"Retell function call: {function_name} with parameters: {parameters}")

        return VoiceResponse(
            text=f"Processing your {function_name} request now.",
            function_call={"name": function_name, "arguments": parameters},
        )

    async def handle_call_end(self, call_id: str, duration: int, reason: str) -> None:
        """Handle call termination."""
        logger.info(f"Retell call ended: {call_id}, duration: {duration}s, reason: {reason}")

    async def get_transcript(self, call_id: str) -> list:
        """Retrieve full call transcript from Retell AI."""
        try:
            response = await self._retell_request("GET", f"/v1/calls/{call_id}/transcript")

            transcript_segments = [
                {
                    "text": segment.get("text", ""),
                    "is_final": segment.get("is_final", False),
                    "confidence": segment.get("confidence", 0.0),
                    "start_time": segment.get("start_time", 0.0),
                    "end_time": segment.get("end_time", 0.0),
                }
                for segment in response.get("transcript", [])
            ]

            return transcript_segments

        except Exception as exc:
            logger.error(f"Retell transcript fetch failed: {exc}")
            return []

    async def get_recording_url(self, call_id: str) -> str | None:
        """Get recording URL for a completed call from Retell AI."""
        try:
            response = await self._retell_request("GET", f"/v1/calls/{call_id}/recording")
            return response.get("recording_url")

        except Exception as exc:
            logger.error(f"Retell recording fetch failed: {exc}")
            return None

    async def webhook_handler(self, payload: dict) -> VoiceResponse | None:
        """Process an incoming webhook from Retell AI."""
        event_type = payload.get("event", "")
        call_id = payload.get("call_id", "")

        logger.info(f"Retell webhook: {event_type} for call {call_id}")

        if event_type == "call_started":
            return await self.handle_call_start(
                call_id,
                payload.get("caller_number", "unknown"),
                payload.get("callee_number", ""),
            )

        elif event_type == "speech_transcribed":
            return await self.handle_speech(
                call_id,
                payload.get("transcript", ""),
                payload.get("is_final", False),
            )

        elif event_type == "function_called":
            return await self.handle_function_call(
                call_id,
                payload.get("function_name", ""),
                payload.get("parameters", {}),
            )

        elif event_type == "call_ended":
            await self.handle_call_end(
                call_id,
                payload.get("duration_seconds", 0),
                payload.get("reason", "completed"),
            )
            return None

        return None

    async def _retell_request(self, method: str, endpoint: str, payload: dict | None = None) -> dict:
        """Make a request to the Retell AI API."""
        import httpx

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=headers, timeout=10)
            else:
                response = await client.post(url, headers=headers, json=payload, timeout=10)

            response.raise_for_status()
            return response.json()
