"""Receptionist authentication handler.

Combines voice provider and OTP verification to authenticate callers
before routing them to the appropriate service.
"""

import logging
from typing import Any

from providers.voice.base import CallRequest, CallStatus, ProviderRateLimiter

from .verification_handler import VoiceVerifyHandler

logger = logging.getLogger("receptionist.handler")


class ReceptionistAuthenticator:
    """Handles full OTP verification flow for incoming calls.

    Uses a voice provider to send codes and a verification store
    to verify them. Once verified, the caller is routed to the
    appropriate service (appointment, FAQ, etc.).
    """

    def __init__(
        self,
        rate_limiter: ProviderRateLimiter,
        voice_handler: VoiceVerifyHandler,
    ) -> None:
        self.rate_limiter = rate_limiter
        self.voice_handler = voice_handler
        self._active_calls: dict[str, str] = {}  # call_id -> phone_number

    async def start_verification(
        self,
        call_id: str,
        phone_number: str,
        send_func,
    ) -> bool:
        """Start OTP verification for an incoming call.

        Generates a code, stores it, and sends it via the voice provider.
        Returns True if the code was sent successfully.
        """
        # Check rate limit before sending
        await self.rate_limiter.wait_if_blocked()

        code = self._generate_code()
        await self.voice_handler.voice_client.set_code(call_id, code)

        return await self.voice_handler.send_otp(phone_number, code, send_func)

    async def verify_call(
        self,
        call_id: str,
        code: str,
    ) -> bool:
        """Verify a verification code for an active call."""
        return await self.voice_handler.verify_code(call_id, code)

    def is_verified(self, call_id: str) -> bool:
        """Check if a call has been verified."""
        return self.voice_handler.is_verified(call_id)

    def _generate_code(self) -> str:
        """Generate a random 6-digit OTP code."""
        import random

        return "".join(str(x) for x in range(6))


def build_bot(token: str) -> ReceptionistAuthenticator:
    """Create a ReceptionistAuthenticator with default settings."""
    from providers.rate_limit import ProviderRateLimiter

    rate_limiter = ProviderRateLimiter(rate_limit=30, rate_window=60, max_concurrency=5)

    return ReceptionistAuthenticator(
        rate_limiter=rate_limiter,
        voice_handler=voice_handler,
    )
