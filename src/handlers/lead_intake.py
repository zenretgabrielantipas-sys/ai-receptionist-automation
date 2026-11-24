"""
Lead Intake Handler

Handles caller lead capture, qualification scoring, CRM storage,
and caller recognition (returning caller detection).
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from config.settings import settings

logger = logging.getLogger("receptionist.lead_intake")


class LeadIntakeHandler:
    """Handles lead capture, qualification, and CRM storage."""

    def __init__(self):
        self.settings = settings
        # In-memory cache for caller recognition (use Redis in production)
        self._caller_cache: dict[str, dict] = {}

    async def capture_lead(
        self,
        call_id: str,
        name: str,
        phone: str,
        email: str | None = None,
        company: str | None = None,
        notes: str | None = None,
        urgency: str = "normal",
        call_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Capture a lead from a caller.

        Args:
            call_id: Call identifier
            name: Caller name
            phone: Caller phone number
            email: Optional email address
            company: Optional company name
            notes: Optional notes from call
            urgency: Lead urgency level (low, normal, high, urgent)
            call_context: Optional context from conversation

        Returns:
            Dict with save result and record ID
        """
        lead_data = {
            "call_id": call_id,
            "name": name,
            "phone": phone,
            "email": email or "",
            "company": company or "",
            "notes": notes or "",
            "urgency": urgency,
            "source": "AI Receptionist",
            "created_at": datetime.now(UTC).isoformat(),
            "qualification_score": self._score_lead(
                urgency=urgency,
                has_email=bool(email),
                has_company=bool(company),
                has_notes=bool(notes),
            ),
        }

        # Save to CRM
        crm_result = await self._save_to_crm(lead_data)

        # Update caller cache for recognition
        self._caller_cache[phone] = {
            "name": name,
            "phone": phone,
            "email": email,
            "company": company,
            "last_call": call_id,
            "lead_score": lead_data["qualification_score"],
            "call_count": self._caller_cache.get(phone, {}).get("call_count", 0) + 1,
        }

        logger.info(
            "Lead captured: %s (%s) - score: %d",
            name,
            phone,
            lead_data["qualification_score"],
        )

        return {
            "saved": crm_result.get("saved", False),
            "record_id": crm_result.get("record_id"),
            "lead_score": lead_data["qualification_score"],
            "urgency": urgency,
            "error": crm_result.get("error"),
        }

    async def recognize_caller(self, phone: str) -> dict[str, Any] | None:
        """Check if caller is a returning caller from CRM/cache.

        Args:
            phone: Caller phone number

        Returns:
            Caller info dict if found, None otherwise
        """
        # Check in-memory cache first
        if phone in self._caller_cache:
            cached = self._caller_cache[phone]
            cached["is_returning"] = True
            return cached

        # Try CRM lookup
        if settings.airtable_api_key:
            try:
                crm_result = await self._lookup_caller_in_crm(phone)
                if crm_result.get("found"):
                    self._caller_cache[phone] = crm_result
                    return crm_result
            except Exception as exc:
                logger.error("Caller lookup failed: %s", exc)

        return None

    async def _save_to_crm(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """Save lead to Airtable CRM."""
        if not settings.airtable_api_key:
            logger.warning("Airtable not configured")
            return {"saved": False, "error": "CRM not configured"}

        try:
            url = (
                f"https://api.airtable.com/v0/"
                f"{settings.airtable_base_id}/{settings.airtable_table_leads}"
            )
            headers = {
                "Authorization": f"Bearer {settings.airtable_api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, headers=headers, json={"fields": lead_data}, timeout=10
                )
                response.raise_for_status()
                result = response.json()
                logger.info("Lead saved to Airtable: %s", result.get("id"))
                return {"saved": True, "record_id": result.get("id")}

        except Exception as exc:
            logger.error("CRM save failed: %s", exc)
            return {"saved": False, "error": str(exc)}

    async def _lookup_caller_in_crm(self, phone: str) -> dict[str, Any]:
        """Look up caller in Airtable CRM by phone number."""
        if not settings.airtable_api_key:
            return {"found": False}

        try:
            import urllib.parse

            phone_encoded = urllib.parse.quote(phone)
            url = (
                f"https://api.airtable.com/v0/"
                f"{settings.airtable_base_id}/{settings.airtable_table_leads}"
                f"?filterByFormula=SEARCH('{phone_encoded}', {{Phone}})>0"
            )
            headers = {
                "Authorization": f"Bearer {settings.airtable_api_key}",
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                result = response.json()

                records = result.get("records", [])
                if records:
                    fields = records[0].get("fields", {})
                    return {
                        "found": True,
                        "name": fields.get("Name", ""),
                        "phone": fields.get("Phone", ""),
                        "email": fields.get("Email", ""),
                        "company": fields.get("Company", ""),
                        "record_id": records[0].get("id"),
                    }

            return {"found": False}

        except Exception as exc:
            logger.error("CRM lookup failed: %s", exc)
            return {"found": False}

    def _score_lead(
        self,
        urgency: str,
        has_email: bool,
        has_company: bool,
        has_notes: bool,
    ) -> int:
        """Score a lead from 0-100 based on qualification factors.

        Args:
            urgency: Urgency level string
            has_email: Whether email was provided
            has_company: Whether company was provided
            has_notes: Whether notes were provided

        Returns:
            Score from 0-100
        """
        score = 0

        # Urgency scoring
        urgency_scores = {"low": 10, "normal": 25, "high": 50, "urgent": 75}
        score += urgency_scores.get(urgency, 25)

        # Completeness scoring
        if has_email:
            score += 10
        if has_company:
            score += 10
        if has_notes:
            score += 5

        return min(score, 100)

    def get_lead_tier(self, score: int) -> str:
        """Categorize lead score into tier.

        Args:
            score: Lead score 0-100

        Returns:
            Tier string: 'cold', 'warm', 'hot', 'urgent'
        """
        if score >= 75:
            return "urgent"
        elif score >= 50:
            return "hot"
        elif score >= 25:
            return "warm"
        else:
            return "cold"
