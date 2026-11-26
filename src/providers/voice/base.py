"""
Voice provider base class for AI Receptionist.

Defines the abstract interface that all voice providers must implement.
Providers handle speech-to-text, text-to-speech, intent detection,
and function calling for voice conversations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class CallEvent:
    """Represents a voice call event."""

    call_id: str
    event_type: str  # call_start, speech_start, speech_end, function_call, call_end
    payload: dict
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC).isoformat()


@dataclass
class TranscriptSegment:
    """A single transcript segment from speech-to-text."""

    text: str
    is_final: bool
    confidence: float
    start_time: float
    end_time: float


@dataclass
class VoiceResponse:
    """Response from voice provider."""

    text: str | None = None  # Text to speak to caller
    audio_url: str | None = None  # Pre-recorded audio URL
    action: str | None = None  # Action to take (transfer, hangup, etc.)
    function_call: dict | None = None  # Function call request
    end_call: bool = False


class BaseVoiceProvider(ABC):
    """Abstract base class for voice providers."""

    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.config = kwargs

    @abstractmethod
    async def handle_call_start(
        self, call_id: str, caller_number: str, callee_number: str
    ) -> VoiceResponse:
        """Handle an incoming call start event."""
        ...

    @abstractmethod
    async def handle_speech(
        self, call_id: str, transcript: str, is_final: bool
    ) -> VoiceResponse:
        """Handle transcribed speech from the caller."""
        ...

    @abstractmethod
    async def handle_function_call(
        self, call_id: str, function_name: str, parameters: dict
    ) -> VoiceResponse:
        """Handle a function call request from the voice agent."""
        ...

    @abstractmethod
    async def handle_call_end(self, call_id: str, duration: int, reason: str) -> None:
        """Handle call termination."""
        ...

    @abstractmethod
    async def get_transcript(self, call_id: str) -> list[TranscriptSegment]:
        """Retrieve full call transcript."""
        ...

    @abstractmethod
    async def get_recording_url(self, call_id: str) -> str | None:
        """Get recording URL for a completed call."""
        ...

    @abstractmethod
    async def webhook_handler(self, payload: dict) -> VoiceResponse | None:
        """Process an incoming webhook from the voice provider."""
        ...
