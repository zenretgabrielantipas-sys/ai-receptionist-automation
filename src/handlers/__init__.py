"""
AI Receptionist Automation - Handler Modules

Each handler implements a specific workflow stage:
- appointment: Calendar scheduling, availability check, booking
- faq: Knowledge base Q&A
- lead_intake: Lead capture and CRM
- notification: SMS, email, Slack notifications
- analytics: Call analytics and reporting
"""

from .analytics import AnalyticsHandler
from .appointment import AppointmentHandler
from .faq import FAQHandler
from .lead_intake import LeadIntakeHandler
from .notification import NotificationHandler

__all__ = [
    "AnalyticsHandler",
    "AppointmentHandler",
    "FAQHandler",
    "LeadIntakeHandler",
    "NotificationHandler",
]
