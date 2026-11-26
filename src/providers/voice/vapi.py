"""
VAPI Voice Provider Implementation.

VAPI (vapi.ai) provides real-time voice AI with:
- Speech-to-text and text-to-speech
- Intent detection
- Function calling
- Call recording and transcription
"""

import logging

import httpx

from config.settings import settings
from providers.voice.base import BaseVoiceProvider, VoiceResponse

logger = logging.getLogger("providers.vapi")


class VAPIProvider(BaseVoiceProvider):
    """NVIDIA NIM-powered VAPI voice provider."""

    def __init__(self, api_key: str, assistant_id: str | None = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.assistant_id = assistant_id or settings.vapi_assistant_id
        self.base_url = "https://api.vapi.ai"

    async def handle_call_start(
        self, call_id: str, caller_number: str, callee_number: str
    ) -> VoiceResponse:
        """Handle an incoming call start event via VAPI."""
        logger.info(f"VAPI call started: {call_id} from {caller_number}")

        return VoiceResponse(
            text="Hello, thank you for calling. How can I help you today?",
        )

    async def handle_speech(
        self, call_id: str, transcript: str, is_final: bool
    ) -> VoiceResponse:
        """Handle transcribed speech from the caller via VAPI."""
        logger.debug(f"VAPI speech: call_id={call_id}, transcript={transcript[:50]}..., final={is_final}")

        if not is_final:
            return VoiceResponse(text=None)  # Intermediate result, no response needed

        # Intent detection via VAPI
        intent_payload = {
            "call_id": call_id,
            "transcript": transcript,
            "assistant_id": self.assistant_id,
        }

        try:
            response = await self._vapi_request("POST", "/intent", intent_payload)

            intent = response.get("intent", "other")
            entities = response.get("entities", {})

            logger.info(f"VAPI intent detected: {intent} (confidence: {response.get('confidence', 0.0)})")

            return VoiceResponse(
                text=f"I understand you want to {intent}. Let me help you with that.",
                function_call={"name": f"handle_{intent}", "arguments": entities},
            )

        except Exception as exc:
            logger.error(f"VAPI intent detection failed: {exc}")
            return VoiceResponse(
                text="I'm sorry, I didn't understand that. Could you please rephrase?",
            )

    async def handle_function_call(
        self, call_id: str, function_name: str, parameters: dict
    ) -> VoiceResponse:
        """Handle a function call request from VAPI."""
        logger.info(f"VAPI function call: {function_name} with parameters: {parameters}")

        return VoiceResponse(
            text=f"I'm processing your {function_name} request.",
            function_call={"name": function_name, "arguments": parameters},
        )

    async def handle_call_end(self, call_id: str, duration: int, reason: str) -> None:
        """Handle call termination."""
        logger.info(f"VAPI call ended: {call_id}, duration: {duration}s, reason: {reason}")

    async def get_transcript(self, call_id: str) -> list:
        """Retrieve full call transcript from VAPI."""
        try:
            response = await self._vapi_request("GET", f"/calls/{call_id}/transcript")

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
            logger.error(f"VAPI transcript fetch failed: {exc}")
            return []

    async def get_recording_url(self, call_id: str) -> str | None:
        """Get recording URL for a completed call from VAPI."""
        try:
            response = await self._vapi_request("GET", f"/calls/{call_id}/recording")
            return response.get("recording_url")

        except Exception as exc:
            logger.error(f"VAPI recording fetch failed: {exc}")
            return None

    async def webhook_handler(self, payload: dict) -> VoiceResponse | None:
        """Process an incoming webhook from VAPI."""
        event_type = payload.get("event", "")
        call_id = payload.get("call_id", "")

        logger.info(f"VAPI webhook: {event_type} for call {call_id}")

        if event_type == "call-start":
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

        elif event_type == "function-call":
            return await self.handle_function_call(
                call_id,
                payload.get("function_name", ""),
                payload.get("parameters", {}),
            )

        elif event_type == "call-end":
            await self.handle_call_end(
                call_id,
                payload.get("duration", 0),
                payload.get("reason", "completed"),
            )
            return None

        return None

    async def _vapi_request(self, method: str, endpoint: str, payload: dict | None = None) -> dict:
        """Make a request to the VAPI API."""

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
