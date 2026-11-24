"""
Database Layer for AI Receptionist Automation

SQLite-based persistence layer for call records, leads, and analytics.
In production, this should be replaced with PostgreSQL.
"""

import asyncio
import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger("receptionist.database")

# Default database path
DEFAULT_DB_PATH = "./data/receptionist.db"


def get_db_path() -> str:
    """Get the database file path."""
    import os

    return os.getenv("RECEPTIONIST_DB_PATH", DEFAULT_DB_PATH)


def init_db(db_path: str | None = None) -> None:
    """Initialize the database with required tables."""
    path = db_path or get_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Calls table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            call_id TEXT PRIMARY KEY,
            caller_number TEXT,
            callee_number TEXT,
            started_at TEXT,
            ended_at TEXT,
            status TEXT,
            intent TEXT,
            outcome TEXT,
            duration_seconds REAL,
            transcript TEXT,
            summary TEXT,
            has_audio INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Leads table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT,
            name TEXT,
            phone TEXT,
            email TEXT,
            company TEXT,
            notes TEXT,
            urgency TEXT,
            qualification_score INTEGER,
            source TEXT DEFAULT 'AI Receptionist',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Appointments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT,
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT,
            requested_datetime TEXT,
            duration_minutes INTEGER,
            service_type TEXT,
            event_id TEXT,
            calendar_link TEXT,
            status TEXT DEFAULT 'confirmed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Transcripts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            transcript_id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT,
            speaker TEXT,
            text TEXT,
            timestamp TEXT,
            confidence REAL
        )
    """)

    # Analytics events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT,
            event_name TEXT,
            event_data TEXT,
            tracked_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized: %s", path)


@contextmanager
def get_connection(db_path: str | None = None):
    """Get a database connection with context manager."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


async def async_init_db(db_path: str | None = None) -> None:
    """Async wrapper for database initialization."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, init_db, db_path)


class CallRecord:
    """Database operations for call records."""

    @staticmethod
    def create(
        call_id: str,
        caller_number: str,
        callee_number: str,
        started_at: str,
    ) -> None:
        """Create a new call record."""
        path = get_db_path()
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO calls (call_id, caller_number, callee_number, started_at, status)
                VALUES (?, ?, ?, ?, 'active')
                """,
                (call_id, caller_number, callee_number, started_at),
            )
            conn.commit()

    @staticmethod
    def update(
        call_id: str,
        **updates: Any,
    ) -> None:
        """Update a call record fields."""
        path = get_db_path()
        if not updates:
            return

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = [*list(updates.values()), call_id]

        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE calls SET {set_clause} WHERE call_id = ?",
                values,
            )
            conn.commit()

    @staticmethod
    def get(call_id: str) -> dict[str, Any] | None:
        """Get a call record by ID."""
        path = get_db_path()
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def list_all(limit: int = 100) -> list[dict[str, Any]]:
        """List call records."""
        path = get_db_path()
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM calls ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]


class LeadRecord:
    """Database operations for lead records."""

    @staticmethod
    def create(
        call_id: str,
        name: str,
        phone: str,
        email: str | None = None,
        company: str | None = None,
        notes: str | None = None,
        urgency: str = "normal",
        qualification_score: int = 0,
    ) -> int:
        """Create a new lead record."""
        path = get_db_path()
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO leads (call_id, name, phone, email, company, notes, urgency, qualification_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    name,
                    phone,
                    email,
                    company,
                    notes,
                    urgency,
                    qualification_score,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_by_phone(phone: str) -> dict[str, Any] | None:
        """Get lead by phone number."""
        path = get_db_path()
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM leads WHERE phone = ? ORDER BY created_at DESC LIMIT 1",
                (phone,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def list_all(limit: int = 100) -> list[dict[str, Any]]:
        """List lead records."""
        path = get_db_path()
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM leads ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]


class AppointmentRecord:
    """Database operations for appointment records."""

    @staticmethod
    def create(
        call_id: str,
        customer_name: str,
        customer_phone: str,
        customer_email: str | None,
        requested_datetime: str,
        duration_minutes: int,
        service_type: str,
        event_id: str | None = None,
        calendar_link: str | None = None,
    ) -> int:
        """Create a new appointment record."""
        path = get_db_path()
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO appointments
                (call_id, customer_name, customer_phone, customer_email,
                 requested_datetime, duration_minutes, service_type,
                 event_id, calendar_link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    customer_name,
                    customer_phone,
                    customer_email,
                    requested_datetime,
                    duration_minutes,
                    service_type,
                    event_id,
                    calendar_link,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def list_all(limit: int = 100) -> list[dict[str, Any]]:
        """List appointment records."""
        path = get_db_path()
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM appointments ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]


class TranscriptRecord:
    """Database operations for transcript records."""

    @staticmethod
    def create(
        call_id: str,
        speaker: str,
        text: str,
        timestamp: str,
        confidence: float | None = None,
    ) -> int:
        """Create a transcript entry."""
        path = get_db_path()
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO transcripts (call_id, speaker, text, timestamp, confidence)
                VALUES (?, ?, ?, ?, ?)
                """,
                (call_id, speaker, text, timestamp, confidence),
            )
            conn.commit()
            return cursor.lastrowid


class AnalyticsEvent:
    """Database operations for analytics events."""

    @staticmethod
    def create(
        call_id: str,
        event_name: str,
        event_data: dict[str, Any] | None = None,
    ) -> int:
        """Create an analytics event."""
        path = get_db_path()
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO analytics_events (call_id, event_name, event_data)
                VALUES (?, ?, ?)
                """,
                (call_id, event_name, json.dumps(event_data or {})),
            )
            conn.commit()
            return cursor.lastrowid
