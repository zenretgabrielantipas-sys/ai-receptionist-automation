"""
Voice provider factory with automatic failover.

Creates and manages voice provider instances with automatic failover
between VAPI (primary) and Retell AI (backup).
"""

import logging
import os
import sys
from typing import ClassVar

# Ensure config.settings resolves to our package's config/settings.py
# regardless of pytest rootdir insertion order.
_reception_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _reception_root not in sys.path:
    sys.path.insert(0, _reception_root)

from config.settings import settings
from providers.voice.base import BaseVoiceProvider
from providers.voice.retell import RetellProvider
from providers.voice.vapi import VAPIProvider

logger = logging.getLogger("providers.voice")


class VoiceProviderFactory:
    """Factory for creating and managing voice provider instances."""

    _instances: ClassVar[dict[str, BaseVoiceProvider]] = {}

    @classmethod
    def get_provider(
        self, provider_name: str | None = None
    ) -> BaseVoiceProvider:
        """Get or create a voice provider instance."""

        provider_name = provider_name or settings.voice_provider

        if provider_name in self._instances:
            return self._instances[provider_name]

        if provider_name == "vapi":
            provider = VAPIProvider(
                api_key=settings.vapi_api_key,
                assistant_id=settings.vapi_assistant_id,
            )
        elif provider_name == "retell":
            provider = RetellProvider(
                api_key=settings.retell_api_key,
                agent_id=settings.retell_agent_id,
            )
        else:
            raise ValueError(f"Unknown voice provider: {provider_name}")

        self._instances[provider_name] = provider
        logger.info(f"Voice provider initialized: {provider_name}")
        return provider

    @classmethod
    def get_primary_provider(cls) -> BaseVoiceProvider:
        """Get the primary voice provider."""
        return cls.get_provider(settings.voice_provider)

    @classmethod
    def get_fallback_provider(cls) -> BaseVoiceProvider | None:
        """Get the fallback voice provider if configured."""
        fallback = settings.voice_fallback_provider
        if fallback and fallback != settings.voice_provider:
            return cls.get_provider(fallback)
        return None

    @classmethod
    def get_voice_voices(cls) -> dict[str, str]:
        """Get configured voice mappings for different call types."""
        return {
            "sales": settings.voice_sales_voice,
            "support": settings.voice_support_voice,
            "urgent": settings.voice_urgent_voice,
            "default": settings.voice_voices.split(",")[0]
            if settings.voice_voices
            else "default",
        }


class VoiceProviderFailover:
    """Manages voice provider failover with automatic recovery."""

    def __init__(self):
        self.primary = VoiceProviderFactory.get_primary_provider()
        self.fallback = VoiceProviderFactory.get_fallback_provider()
        self.primary_healthy = True
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3

    async def handle_call_start(
        self, call_id: str, caller_number: str, callee_number: str
    ):
        """Handle call start with failover support."""
        try:
            return await self.primary.handle_call_start(
                call_id, caller_number, callee_number
            )
        except Exception as exc:
            logger.error(f"Primary provider failed on call start: {exc}")
            self.consecutive_failures += 1

            if self.consecutive_failures >= self.max_consecutive_failures:
                self.primary_healthy = False
                logger.warning("Switching to fallback voice provider")

            if self.fallback:
                return await self.fallback.handle_call_start(
                    call_id, caller_number, callee_number
                )

            raise

    async def handle_speech(self, call_id: str, transcript: str, is_final: bool):
        """Handle speech with failover support."""
        try:
            return await self.primary.handle_speech(call_id, transcript, is_final)
        except Exception as exc:
            logger.error(f"Primary provider failed on speech: {exc}")
            self.consecutive_failures += 1

            if self.consecutive_failures >= self.max_consecutive_failures:
                self.primary_healthy = False

            if self.fallback:
                return await self.fallback.handle_speech(call_id, transcript, is_final)

            raise

    async def handle_function_call(
        self, call_id: str, function_name: str, parameters: dict
    ):
        """Handle function call with failover support."""
        try:
            return await self.primary.handle_function_call(
                call_id, function_name, parameters
            )
        except Exception as exc:
            logger.error(f"Primary provider failed on function call: {exc}")
            self.consecutive_failures += 1

            if self.consecutive_failures >= self.max_consecutive_failures:
                self.primary_healthy = False

            if self.fallback:
                return await self.fallback.handle_function_call(
                    call_id, function_name, parameters
                )

            raise

    async def handle_call_end(self, call_id: str, duration: int, reason: str):
        """Handle call end with failover support."""
        try:
            await self.primary.handle_call_end(call_id, duration, reason)
        except Exception as exc:
            logger.error(f"Primary provider failed on call end: {exc}")
            self.consecutive_failures += 1

            if self.consecutive_failures >= self.max_consecutive_failures:
                self.primary_healthy = False

            if self.fallback:
                await self.fallback.handle_call_end(call_id, duration, reason)

    async def get_transcript(self, call_id: str):
        """Get transcript with failover support."""
        try:
            return await self.primary.get_transcript(call_id)
        except Exception as exc:
            logger.error(f"Primary provider failed on transcript: {exc}")
            if self.fallback:
                return await self.fallback.get_transcript(call_id)
            return []

    async def get_recording_url(self, call_id: str) -> str | None:
        """Get recording URL with failover support."""
        try:
            return await self.primary.get_recording_url(call_id)
        except Exception as exc:
            logger.error(f"Primary provider failed on recording: {exc}")
            if self.fallback:
                return await self.fallback.get_recording_url(call_id)
            return None

    async def webhook_handler(self, payload: dict):
        """Route webhook through primary provider with failover."""
        try:
            return await self.primary.webhook_handler(payload)
        except Exception as exc:
            logger.error(f"Primary provider webhook failed: {exc}")
            self.consecutive_failures += 1

            if self.consecutive_failures >= self.max_consecutive_failures:
                self.primary_healthy = False

            if self.fallback:
                return await self.fallback.webhook_handler(payload)

            return None

    def reset_failover(self):
        """Reset failover state (called on successful operation)."""
        self.consecutive_failures = 0
        self.primary_healthy = True


# Singleton instance
voice_failover = VoiceProviderFailover()
