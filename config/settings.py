"""
Configuration management for AI Receptionist Automation.

Loads environment variables from .env file and provides typed access
to all configuration values required by the automation workflow.
"""

import os
from typing import Any, Dict, List, Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        pass  # Fallback if python-dotenv not installed


class Settings:
    """Centralized settings for the AI receptionist automation."""

    def __init__(self, env_file: Optional[str] = None):
        if env_file is None:
            env_file = os.path.join(os.path.dirname(__file__), ".env")
        load_dotenv(env_file)

    # ── Telephony & Voice ──
    @property
    def twilio_account_sid(self) -> str:
        return os.getenv("TWILIO_ACCOUNT_SID", "")

    @property
    def twilio_auth_token(self) -> str:
        return os.getenv("TWILIO_AUTH_TOKEN", "")

    @property
    def twilio_phone_number(self) -> str:
        return os.getenv("TWILIO_PHONE_NUMBER", "")

    @property
    def twilio_messaging_service_sid(self) -> str:
        return os.getenv("TWILIO_MESSAGING_SERVICE_SID", "")

    @property
    def vapi_api_key(self) -> str:
        return os.getenv("VAPI_API_KEY", "")

    @property
    def vapi_assistant_id(self) -> str:
        return os.getenv("VAPI_ASSISTANT_ID", "")

    @property
    def retell_api_key(self) -> str:
        return os.getenv("RETELL_API_KEY", "")

    @property
    def retell_agent_id(self) -> str:
        return os.getenv("RETELL_AGENT_ID", "")

    @property
    def voice_provider(self) -> str:
        """Primary voice provider: vapi or retell."""
        return os.getenv("VOICE_PROVIDER", "vapi")

    @property
    def voice_fallback_provider(self) -> str:
        """Fallback voice provider."""
        return os.getenv("VOICE_FALLBACK_PROVIDER", "retell")

    @property
    def voice_voices(self) -> List[str]:
        """Available voice IDs for different call types."""
        raw = os.getenv("VOICE_VOICES", "default")
        return [v.strip() for v in raw.split(",") if v.strip()]

    @property
    def voice_sales_voice(self) -> str:
        return os.getenv("VOICE_SALES_VOICE", "default")

    @property
    def voice_support_voice(self) -> str:
        return os.getenv("VOICE_SUPPORT_VOICE", "default")

    @property
    def voice_urgent_voice(self) -> str:
        return os.getenv("VOICE_URGENT_VOICE", "default")

    @property
    def multi_language(self) -> bool:
        return os.getenv("MULTI_LANGUAGE", "true").lower() == "true"

    @property
    def urgency_detection(self) -> bool:
        return os.getenv("URGENCY_DETECTION", "true").lower() == "true"

    @property
    def polite_closing(self) -> bool:
        return os.getenv("POLITE_CLOSING", "true").lower() == "true"

    # ── Automation Engine ──
    @property
    def n8n_webhook_url(self) -> str:
        return os.getenv("N8N_WEBHOOK_URL", "")

    @property
    def n8n_api_key(self) -> str:
        return os.getenv("N8N_API_KEY", "")

    @property
    def test_mode(self) -> bool:
        return os.getenv("TEST_MODE", "true").lower() == "true"

    @property
    def auto_restart(self) -> bool:
        return os.getenv("AUTO_RESTART", "true").lower() == "true"

    # ── Calendar ──
    @property
    def google_calendar_credentials_path(self) -> str:
        return os.getenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "")

    @property
    def google_calendar_id(self) -> str:
        return os.getenv("GOOGLE_CALENDAR_ID", "")

    @property
    def google_client_id(self) -> str:
        return os.getenv("GOOGLE_CLIENT_ID", "")

    @property
    def google_client_secret(self) -> str:
        return os.getenv("GOOGLE_CLIENT_SECRET", "")

    @property
    def google_redirect_uri(self) -> str:
        return os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

    @property
    def send_calendar_invites(self) -> bool:
        return os.getenv("SEND_CALENDAR_invites", "true").lower() == "true"

    # ── CRM ──
    @property
    def airtable_api_key(self) -> str:
        return os.getenv("AIRTABLE_API_KEY", "")

    @property
    def airtable_base_id(self) -> str:
        return os.getenv("AIRTABLE_BASE_ID", "")

    @property
    def airtable_table_leads(self) -> str:
        return os.getenv("AIRTABLE_TABLE_LEADS", "")

    @property
    def airtable_table_calls(self) -> str:
        return os.getenv("AIRTABLE_TABLE_CALLS", "")

    @property
    def hubspot_api_key(self) -> str:
        return os.getenv("HUBSPOT_API_KEY", "")

    @property
    def lead_qualification_scoring(self) -> bool:
        return os.getenv("LEAD_QUALIFICATION_SCORING", "true").lower() == "true"

    @property
    def caller_recognition(self) -> bool:
        return os.getenv("CALLER_RECOGNITION", "true").lower() == "true"

    @property
    def identity_verification_appointments(self) -> bool:
        return os.getenv("IDENTITY_VERIFICATION_APPOINTMENTS", "true").lower() == "true"

    @property
    def google_contacts_sync(self) -> bool:
        return os.getenv("GOOGLE_CONTACTS_SYNC", "true").lower() == "true"

    # ── Notifications ──
    @property
    def sendgrid_api_key(self) -> str:
        return os.getenv("SENDGRID_API_KEY", "")

    @property
    def sendgrid_from_email(self) -> str:
        return os.getenv("SENDGRID_FROM_EMAIL", "receptionist@yourdomain.com")

    @property
    def resend_api_key(self) -> str:
        return os.getenv("RESEND_API_KEY", "")

    @property
    def slack_webhook_url(self) -> str:
        return os.getenv("SLACK_WEBHOOK_URL", "")

    @property
    def slack_channel(self) -> str:
        return os.getenv("SLACK_CHANNEL", "#reception-alerts")

    @property
    def slack_bot_token(self) -> str:
        return os.getenv("SLACK_BOT_TOKEN", "")

    # ── Transcripts & Recordings ──
    @property
    def call_recording(self) -> bool:
        return os.getenv("CALL_RECORDING", "true").lower() == "true"

    @property
    def voicemail_transcription(self) -> bool:
        return os.getenv("VOICEMAIL_TRANSCRIPTION", "true").lower() == "true"

    @property
    def transcript_retention_days(self) -> int:
        return int(os.getenv("TRANSCRIPT_RETENTION_DAYS", "30"))

    @property
    def transcript_searchable(self) -> bool:
        return os.getenv("TRANSCRIPT_SEARCHABLE", "true").lower() == "true"

    @property
    def call_ai_summary(self) -> bool:
        return os.getenv("CALL_AI_SUMMARY", "true").lower() == "true"

    # ── Notifications & Alerts ──
    @property
    def sms_notifications_enabled(self) -> bool:
        return os.getenv("SMS_NOTIFICATIONS_ENABLED", "true").lower() == "true"

    @property
    def email_notifications_enabled(self) -> bool:
        return os.getenv("EMAIL_NOTIFICATIONS_ENABLED", "true").lower() == "true"

    @property
    def owner_sms_reminders(self) -> bool:
        return os.getenv("OWNER_SMS_REMINDERS", "true").lower() == "true"

    @property
    def appointment_reminder_24h(self) -> bool:
        return os.getenv("APPOINTMENT_REMINDER_24H", "true").lower() == "true"

    @property
    def appointment_reminder_1h(self) -> bool:
        return os.getenv("APPOINTMENT_REMINDER_1H", "true").lower() == "true"

    @property
    def post_call_surveys(self) -> bool:
        return os.getenv("POST_CALL_SURVEYS", "true").lower() == "true"

    @property
    def post_call_email_followup(self) -> bool:
        return os.getenv("POST_CALL_EMAIL_FOLLOWUP", "true").lower() == "true"

    # ── Analytics & Reporting ──
    @property
    def google_sheets_id(self) -> str:
        return os.getenv("GOOGLE_SHEETS_ID", "")

    @property
    def mixpanel_api_key(self) -> str:
        return os.getenv("MIXPANEL_API_KEY", "")

    @property
    def mixpanel_secret(self) -> str:
        return os.getenv("MIXPANEL_SECRET", "")

    @property
    def daily_report_enabled(self) -> bool:
        return os.getenv("DAILY_REPORT_ENABLED", "true").lower() == "true"

    @property
    def file_sharing_enabled(self) -> bool:
        return os.getenv("FILE_SHARING_ENABLED", "true").lower() == "true"

    # ── Application ──
    @property
    def app_host(self) -> str:
        return os.getenv("APP_HOST", "0.0.0.0")

    @property
    def app_port(self) -> int:
        return int(os.getenv("APP_PORT", "8000"))

    @property
    def app_debug(self) -> bool:
        return os.getenv("APP_DEBUG", "False").lower() == "true"

    @property
    def webhook_secret(self) -> str:
        return os.getenv("WEBHOOK_SECRET", "")

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def log_file(self) -> str:
        return os.getenv("LOG_FILE", "./logs/receptionist.log")

    @property
    def timezone(self) -> str:
        return os.getenv("TIMEZONE", "America/New_York")

    # 24/7 means no business hour restrictions
    @property
    def business_24_7(self) -> bool:
        return os.getenv("BUSINESS_24_7", "true").lower() == "true"

    @property
    def business_hours_start(self) -> int:
        return int(os.getenv("BUSINESS_HOURS_START", "0"))

    @property
    def business_hours_end(self) -> int:
        return int(os.getenv("BUSINESS_HOURS_END", "23"))

    @property
    def business_days(self) -> List[str]:
        days = os.getenv("BUSINESS_DAYS", "mon,tue,wed,thu,fri,sat,sun")
        return [d.strip().lower() for d in days.split(",")]

    # Multi-channel
    @property
    def phone_enabled(self) -> bool:
        return os.getenv("PHONE_ENABLED", "true").lower() == "true"

    @property
    def web_chat_enabled(self) -> bool:
        return os.getenv("WEB_CHAT_ENABLED", "false").lower() == "true"

    @property
    def web_dashboard_enabled(self) -> bool:
        return os.getenv("WEB_DASHBOARD_ENABLED", "true").lower() == "true"

    # Role-based access
    @property
    def role_based_access(self) -> bool:
        return os.getenv("ROLE_BASED_ACCESS", "true").lower() == "true"

    # Voice IVR
    @property
    def multi_language_ivr(self) -> bool:
        return os.getenv("MULTI_LANGUAGE_IVR", "true").lower() == "true"

    def to_dict(self) -> Dict[str, Any]:
        """Return all settings as a dictionary (masking secrets)."""
        return {
            "twilio_phone_number": self.twilio_phone_number,
            "voice_provider": self.voice_provider,
            "voice_fallback_provider": self.voice_fallback_provider,
            "multi_language": self.multi_language,
            "urgency_detection": self.urgency_detection,
            "polite_closing": self.polite_closing,
            "n8n_webhook_url": self.n8n_webhook_url,
            "test_mode": self.test_mode,
            "auto_restart": self.auto_restart,
            "google_calendar_id": self.google_calendar_id,
            "airtable_base_id": self.airtable_base_id,
            "sendgrid_from_email": self.sendgrid_from_email,
            "slack_channel": self.slack_channel,
            "google_sheets_id": self.google_sheets_id,
            "app_host": self.app_host,
            "app_port": self.app_port,
            "timezone": self.timezone,
            "business_24_7": self.business_24_7,
            "business_days": self.business_days,
            "role_based_access": self.role_based_access,
            "web_dashboard_enabled": self.web_dashboard_enabled,
        }


# Global settings instance
settings = Settings()
