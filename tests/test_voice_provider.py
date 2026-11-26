"""
Tests for Voice Provider implementations (VAPI and Retell) with mocks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.voice.base import CallEvent, VoiceResponse
from providers.voice.retell import RetellProvider
from providers.voice.vapi import VAPIProvider


class TestVAPIProvider:
    """Tests for VAPI voice provider."""

    def setup_method(self):
        self.provider = VAPIProvider(
            api_key="test-key",
            assistant_id="test-assistant-id",
        )

    def test_provider_initialization(self):
        """Provider should initialize with API key and assistant ID."""
        assert self.provider.api_key == "test-key"
        assert self.provider.assistant_id == "test-assistant-id"
        assert self.provider.base_url == "https://api.vapi.ai"

    def test_handle_call_start(self):
        """handle_call_start should return VoiceResponse with greeting."""
        import asyncio

        result = asyncio.run(
            self.provider.handle_call_start("call_1", "+1234567890", "+0987654321")
        )
        assert isinstance(result, VoiceResponse)
        assert result.text == "Hello, thank you for calling. How can I help you today?"

    def test_handle_speech_final(self):
        """handle_speech with is_final=True should return voice response."""
        import asyncio

        result = asyncio.run(
            self.provider.handle_speech("call_1", "I want to book an appointment", True)
        )
        assert isinstance(result, VoiceResponse)
        assert result.text is not None

    def test_handle_speech_not_final(self):
        """handle_speech with is_final=False should return no text."""
        import asyncio

        result = asyncio.run(
            self.provider.handle_speech("call_1", "partial speech", False)
        )
        assert result.text is None

    @pytest.mark.asyncio
    async def test_webhook_handler_call_start(self):
        """webhook_handler should process call-start events."""
        payload = {
            "event": "call-start",
            "call_id": "call_1",
            "caller_number": "+1234567890",
            "callee_number": "+0987654321",
        }
        result = await self.provider.webhook_handler(payload)
        assert isinstance(result, VoiceResponse)
        assert "hello" in result.text.lower() if result.text else False

    @pytest.mark.asyncio
    async def test_webhook_handler_call_end(self):
        """webhook_handler should process call-end events."""
        payload = {
            "event": "call-end",
            "call_id": "call_1",
            "duration": 120,
            "reason": "completed",
        }
        result = await self.provider.webhook_handler(payload)
        assert result is None  # call_end returns None

    @pytest.mark.asyncio
    async def test_get_transcript(self):
        """get_transcript should return list of transcript segments."""
        provider = VAPIProvider(api_key="test-key")

        # Mock the httpx client
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "transcript": [
                    {
                        "text": "Hello",
                        "is_final": True,
                        "confidence": 0.95,
                        "start_time": 0.0,
                        "end_time": 1.5,
                    }
                ]
            }
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await provider.get_transcript("call_1")
            assert len(result) == 1
            assert result[0].text == "Hello"
            assert result[0].is_final is True

    @pytest.mark.asyncio
    async def test_get_recording_url(self):
        """get_recording_url should return URL string."""
        provider = VAPIProvider(api_key="test-key")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"recording_url": "https://example.com/recording.mp3"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await provider.get_recording_url("call_1")
            assert result == "https://example.com/recording.mp3"


class TestRetellProvider:
    """Tests for Retell AI voice provider."""

    def setup_method(self):
        self.provider = RetellProvider(
            api_key="test-key",
            agent_id="test-agent-id",
        )

    def test_provider_initialization(self):
        """Provider should initialize with API key and agent ID."""
        assert self.provider.api_key == "test-key"
        assert self.provider.agent_id == "test-agent-id"
        assert self.provider.base_url == "https://api.retellai.com"

    def test_handle_call_start(self):
        """handle_call_start should return VoiceResponse with greeting."""
        import asyncio

        result = asyncio.run(
            self.provider.handle_call_start("call_1", "+1234567890", "+0987654321")
        )
        assert isinstance(result, VoiceResponse)
        assert "receptionist" in result.text.lower()

    def test_handle_speech_not_final(self):
        """handle_speech with is_final=False should return no text."""
        import asyncio

        result = asyncio.run(
            self.provider.handle_speech("call_1", "partial", False)
        )
        assert result.text is None

    def test_handle_function_call(self):
        """handle_function_call should return VoiceResponse with function_call."""
        import asyncio

        result = asyncio.run(
            self.provider.handle_function_call(
                "call_1", "book_appointment", {"date": "2024-01-15"}
            )
        )
        assert isinstance(result, VoiceResponse)
        assert result.function_call is not None
        assert result.function_call["name"] == "book_appointment"

    @pytest.mark.asyncio
    async def test_webhook_handler_call_start(self):
        """webhook_handler should process call_started events."""
        payload = {
            "event": "call_started",
            "call_id": "call_1",
            "caller_number": "+1234567890",
            "callee_number": "+0987654321",
        }
        result = await self.provider.webhook_handler(payload)
        assert isinstance(result, VoiceResponse)
        assert "ai receptionist" in result.text.lower()


class TestCallEvent:
    """Tests for CallEvent dataclass."""

    def test_call_event_creation(self):
        """CallEvent should store call_id, event_type, and payload."""
        event = CallEvent(
            call_id="call_1",
            event_type="speech",
            payload={"text": "hello"},
        )
        assert event.call_id == "call_1"
        assert event.event_type == "speech"
        assert event.payload == {"text": "hello"}
        assert event.timestamp is not None

    def test_call_event_has_timestamp(self):
        """CallEvent should auto-generate timestamp."""
        event = CallEvent(call_id="call_1", event_type="call_start", payload={})
        assert event.timestamp is not None
        assert len(event.timestamp) > 0

    def test_call_event_is_dataclass(self):
        """CallEvent should be a dataclass with proper attributes."""
        assert hasattr(CallEvent, "__dataclass_fields__")
        assert "call_id" in CallEvent.__dataclass_fields__
        assert "event_type" in CallEvent.__dataclass_fields__
        assert "payload" in CallEvent.__dataclass_fields__
