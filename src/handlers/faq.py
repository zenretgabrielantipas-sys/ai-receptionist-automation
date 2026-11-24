"""
FAQ Handler - Frequently Asked Questions

Handles FAQ inquiries from callers using a configurable knowledge base.
Supports knowledge base lookups via web services or local file.
"""

import logging
from typing import Any, ClassVar

import httpx

from config.settings import settings

logger = logging.getLogger("receptionist.faq")


class FAQHandler:
    """Handles FAQ inquiries from callers."""

    DEFAULT_KNOWLEDGE_BASE_DOCS: ClassVar[dict[str, str]] = {
        "hours": "We are open 24 hours a day, 7 days a week.",
        "pricing": "Please contact us for pricing information. Our receptionist can provide details.",
        "location": "Our business location details are available upon request.",
        "services": "We offer appointment scheduling, lead capture, and general information services.",
        "contact": "You can reach us via the phone number you called, or through our website.",
        "cancel": "To cancel or reschedule an appointment, please call back or use our online portal.",
    }

    def __init__(self):
        self.settings = settings
        self._knowledge_base = dict(self.DEFAULT_KNOWLEDGE_BASE_DOCS)

    async def answer_question(
        self,
        question: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Answer a caller's FAQ question.

        Args:
            question: The caller's question text
            context: Optional context from previous conversation

        Returns:
            Dict with 'answer' text and 'confidence' score
        """
        try:
            lowercase_q = question.lower().strip()

            # Exact match first
            if lowercase_q in self._knowledge_base:
                return {
                    "answer": self._knowledge_base[lowercase_q],
                    "confidence": 0.95,
                    "source": "knowledge_base",
                }

            # Fuzzy match - check if any keyword is in the question
            best_match = None
            best_score = 0.0

            for key, answer in self._knowledge_base.items():
                keywords = key.split()
                matched = sum(1 for kw in keywords if kw in lowercase_q)
                score = matched / len(keywords) if keywords else 0.0

                if score > best_score and score >= 0.5:
                    best_score = score
                    best_match = answer

            if best_match:
                return {
                    "answer": best_match,
                    "confidence": best_score,
                    "source": "knowledge_base_fuzzy",
                }

            # Try external knowledge base API if configured
            if hasattr(self.settings, "kb_api_url") and self.settings.kb_api_url:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            self.settings.kb_api_url,
                            json={"question": question, "context": context},
                            timeout=10,
                        )
                        if response.status_code == 200:
                            result = response.json()
                            return {
                                "answer": result.get("answer", ""),
                                "confidence": result.get("confidence", 0.8),
                                "source": "external_kb",
                            }
                except Exception as exc:
                    logger.error("External KB lookup failed: %s", exc)

            # Default fallback
            return {
                "answer": "I'm not sure about that. Let me connect you with our team who can help.",
                "confidence": 0.0,
                "source": "fallback",
            }

        except Exception as exc:
            logger.error("FAQ handler error: %s", exc)
            return {
                "answer": "I'm having trouble accessing our knowledge base. Let me transfer you to a human representative.",
                "confidence": 0.0,
                "source": "error",
            }

    def add_knowledge_entry(self, question_key: str, answer: str) -> None:
        """Add or update a knowledge base entry."""
        self._knowledge_base[question_key.lower()] = answer
        logger.info("Added FAQ entry: %s", question_key)

    def load_knowledge_base(self, entries: dict[str, str]) -> None:
        """Load multiple knowledge base entries at once."""
        self._knowledge_base.clear()
        self._knowledge_base.update(self.DEFAULT_KNOWLEDGE_BASE_DOCS)
        for key, answer in entries.items():
            self._knowledge_base[key.lower()] = answer
        logger.info("Loaded %d FAQ entries", len(self._knowledge_base))
