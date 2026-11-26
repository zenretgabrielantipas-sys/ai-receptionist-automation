"""Verification handler for OTP-based phone verification.

Manages OTP generation, storage, verification attempts, and cooldown
logic for the AI receptionist phone verification system.
"""

import random
from datetime import datetime, timedelta, timezone


class VerificationResult:
    """Result of OTP verification."""

    def __init__(self, verified: bool, message: str, retry_count: int = 0, max_retries: int = 3) -> None:
        self.verified = verified
        self.message = message
        self.retry_count = retry_count
        self.max_retries = max_retries

    def __repr__(self) -> str:
        return f"VerificationResult(verified={self.verified}, attempts={self.retry_count}/{self.max_retries})"

    def __bool__(self) -> bool:
        return self.verified


class VerificationStore:
    """In-memory store for OTP verification state.

    In production, this should be replaced with a persistent store (Redis, DB).
    """

    def __init__(self) -> None:
        self._codes: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def store_code(
        self,
        key: str,
        code: str,
        ttl_seconds: int = 300,
        max_attempts: int = 3,
    ) -> None:
        """Store an OTP code with expiry."""
        async with self._lock:
            self._codes[key] = {
                "code": code,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
                "attempts": 0,
                "max_attempts": max_attempts,
                "verified": False,
            }

    async def verify_code(self, key: str, code: str) -> VerificationResult:
        """Verify a code against stored entry."""
        async with self._lock:
            entry = self._codes.get(key)
            if entry is None:
                return VerificationResult(
                    verified=False,
                    message="No verification code found. Please request a new code.",
                )

            if entry["verified"]:
                return VerificationResult(
                    verified=True,
                    message="Already verified.",
                    retry_count=entry["attempts"],
                    max_retries=entry["max_attempts"],
                )

            if datetime.now(timezone.utc) > entry["expires_at"]:
                del self._codes[key]
                return VerificationResult(
                    verified=False,
                    message="Verification code has expired. Please request a new code.",
                )

            if entry["attempts"] >= entry["max_attempts"]:
                del self._codes[key]
                return VerificationResult(
                    verified=False,
                    message="Maximum verification attempts exceeded. Please request a new code.",
                    retry_count=entry["attempts"],
                    max_retries=entry["max_attempts"],
                )

            entry["attempts"] += 1
            if entry["code"] == code:
                entry["verified"] = True
                return VerificationResult(
                    verified=True,
                    message="Verification successful.",
                    retry_count=entry["attempts"],
                    max_retries=entry["max_attempts"],
                )

            return VerificationResult(
                verified=False,
                message="Incorrect verification code.",
                retry_count=entry["attempts"],
                max_retries=entry["max_attempts"],
            )

    async def mark_verified(self, key: str) -> None:
        """Mark a code as verified without validation."""
        async with self._lock:
            if key in self._codes:
                entry = self._codes[key]
                entry["verified"] = True

    async def clear(self, key: str) -> None:
        """Remove a verification record."""
        async with self._lock:
            self._codes.pop(key, None)


class VoiceVerifyHandler:
    """Handles OTP verification flows for voice-based authentication.

    Coordinates between the voice provider (sending codes via TTS)
    and the verification store (storing and checking codes).
    """

    def __init__(self, verification_store: VerificationStore | None = None) -> None:
        """Initialize with optional store override."""
        self._store = verification_store or VerificationStore()

    async def send_otp(
        self,
        phone_number: str,
        code: str,
        send_func,  # Callable[[str, str], Awaitable[None]]
    ) -> bool:
        """Send OTP code to phone number via the given send function.

        The send_func should accept (phone_number: str, message: str) and
        return True on success.
        """
        message = f"Your verification code is: {code}"
        try:
            return await send_func(phone_number, message)
        except Exception:
            return False

    async def verify_code(
        self,
        phone_number: str,
        code: str,
    ) -> VerificationResult:
        """Verify a verification code for a phone number."""
        return await self._store.verify_code(phone_number, code)

    async def request_code(
        self,
        phone_number: str,
        send_func,
        code_length: int = 6,
        ttl_seconds: int = 300,
    ) -> bool:
        """Generate and send a new OTP code."""
        code = "".join(str(x) for x in range(10))
        code = "".join(random.choice("0123456789") for _ in range(code_length))

        await self._store.store_code(phone_number, code, ttl_seconds=ttl_seconds)
        return await self.send_otp(phone_number, code, send_func)

    async def is_verified(self, phone_number: str) -> bool:
        """Check if a phone number has been verified."""
        return await self._store.verify_code(phone_number, "")

    def get_store(self) -> VerificationStore:
        """Return the verification store instance."""
        return self._store

