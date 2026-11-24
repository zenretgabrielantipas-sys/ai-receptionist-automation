"""
Analytics Handler

Handles call analytics, daily reports, Mixpanel tracking,
and Google Sheets integration for reporting.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from config.settings import settings

logger = logging.getLogger("receptionist.analytics")


class AnalyticsHandler:
    """Handles call analytics, reporting, and metrics."""

    def __init__(self):
        self.settings = settings
        self._call_events: list[dict[str, Any]] = []

    async def track_call_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Track a call event in analytics systems.

        Args:
            event: Call event data

        Returns:
            Dict with tracking results
        """
        # Store locally
        self._call_events.append(
            {
                **event,
                "tracked_at": datetime.now(UTC).isoformat(),
            }
        )

        # Keep only last 10000 events in memory
        if len(self._call_events) > 10000:
            self._call_events = self._call_events[-10000:]

        results = {}

        # Mixpanel tracking
        if settings.mixpanel_api_key:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.mixpanel.com/track",
                        json={
                            "event": event.get("event_name", "call_handled"),
                            "properties": event,
                        },
                        timeout=10,
                    )
                    results["mixpanel"] = response.status_code == 200
            except Exception as exc:
                logger.error("Mixpanel track failed: %s", exc)
                results["mixpanel"] = {"error": str(exc)}

        # Google Sheets logging (for daily reports)
        if settings.google_sheets_id:
            try:
                await self._append_to_google_sheets(event)
                results["google_sheets"] = "queued"
            except Exception as exc:
                logger.error("Google Sheets append failed: %s", exc)
                results["google_sheets"] = {"error": str(exc)}

        return results

    async def _append_to_google_sheets(self, event: dict[str, Any]) -> None:
        """Append a call event to Google Sheets."""
        # This requires Google Sheets API setup
        # Placeholder for Google Sheets integration
        logger.debug("Google Sheets append: %s", event.get("call_id", "unknown"))

    async def get_call_statistics(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> dict[str, Any]:
        """Get call statistics for a date range.

        Args:
            start_date: ISO 8601 start date
            end_date: ISO 8601 end date

        Returns:
            Dict with call statistics
        """
        events = self._call_events

        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            events = [
                e
                for e in events
                if datetime.fromisoformat(e.get("tracked_at", "1970-01-01")) >= start_dt
            ]

        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            events = [
                e
                for e in events
                if datetime.fromisoformat(e.get("tracked_at", "1970-01-01")) <= end_dt
            ]

        total_calls = len(events)
        outcomes: dict[str, int] = {}
        intents: dict[str, int] = {}
        total_duration = 0

        for event in events:
            outcome = event.get("outcome", "unknown")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

            intent = event.get("intent", "unknown")
            intents[intent] = intents.get(intent, 0) + 1

            duration = event.get("duration_seconds", 0)
            if isinstance(duration, (int, float)):
                total_duration += duration

        avg_duration = total_duration / total_calls if total_calls > 0 else 0

        return {
            "total_calls": total_calls,
            "average_duration_seconds": round(avg_duration, 2),
            "outcomes": outcomes,
            "intents": intents,
            "period": {
                "start": start_date,
                "end": end_date,
            },
        }

    async def generate_daily_report(self) -> dict[str, Any]:
        """Generate daily analytics report.

        Returns:
            Dict with daily report data
        """
        today = datetime.now(UTC).date().isoformat()
        stats = await self.get_call_statistics(
            start_date=f"{today}T00:00:00",
            end_date=f"{today}T23:59:59",
        )

        report = {
            "date": today,
            "total_calls": stats["total_calls"],
            "average_duration": stats["average_duration_seconds"],
            "outcomes": stats["outcomes"],
            "intents": stats["intents"],
            "generated_at": datetime.now(UTC).isoformat(),
        }

        logger.info(
            "Daily report generated: %d calls on %s",
            stats["total_calls"],
            today,
        )

        return report

    async def send_daily_report(self) -> dict[str, Any]:
        """Generate and send daily report via configured channels.

        Returns:
            Dict with report results
        """
        report = await self.generate_daily_report()

        results = {"report": report}

        # Send to Slack if configured
        if settings.slack_webhook_url:
            try:
                from handlers.notification import NotificationHandler

                handler = NotificationHandler()
                slack_result = await handler.send_slack_alert(
                    message=(
                        f"📊 Daily Receptionist Report ({report['date']})\n"
                        f"• Total calls: {report['total_calls']}\n"
                        f"• Avg duration: {report['average_duration']}s\n"
                        f"• Outcomes: {report['outcomes']}"
                    )
                )
                results["slack"] = slack_result
            except Exception as exc:
                logger.error("Slack report failed: %s", exc)

        # Append to Google Sheets if configured
        if settings.google_sheets_id:
            results["google_sheets"] = "queued"

        return report

    def record_call_event(
        self,
        call_id: str,
        event_name: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Synchronously record a call event (for sync contexts).

        Args:
            call_id: Call identifier
            event_name: Event name
            data: Optional event data
        """
        self._call_events.append(
            {
                "call_id": call_id,
                "event_name": event_name,
                "data": data or {},
                "tracked_at": datetime.now(UTC).isoformat(),
            }
        )
