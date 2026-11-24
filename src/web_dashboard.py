"""
Web Dashboard for AI Receptionist Automation

Provides a web-based dashboard for viewing call logs, appointments,
leads, and analytics. Built with FastAPI and Jinja2 templates.
"""

import logging
from typing import Any

from analytics import AnalyticsHandler
from database import (
    AppointmentRecord,
    CallRecord,
    LeadRecord,
    init_db,
)
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config.settings import settings

logger = logging.getLogger("receptionist.dashboard")

router = APIRouter()

# Templates directory
templates = Jinja2Templates(directory="templates")


@router.on_event("startup")
async def startup():
    """Initialize database on startup."""
    try:
        init_db()
        logger.info("Dashboard database initialized")
    except Exception as exc:
        logger.error("Dashboard database init failed: %s", exc)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "title": "AI Receptionist Dashboard"},
    )


@router.get("/api/dashboard/stats")
async def dashboard_stats(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> dict[str, Any]:
    """Get dashboard statistics."""
    try:
        analytics = AnalyticsHandler()
        stats = await analytics.get_call_statistics(
            start_date=start_date,
            end_date=end_date,
        )
        return {
            "success": True,
            "stats": stats,
        }
    except Exception as exc:
        logger.error("Dashboard stats error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/dashboard/calls")
async def dashboard_calls(
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """Get recent call records."""
    try:
        calls = CallRecord.list_all(limit=limit)
        return {
            "success": True,
            "calls": calls,
            "count": len(calls),
        }
    except Exception as exc:
        logger.error("Dashboard calls error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/dashboard/leads")
async def dashboard_leads(
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """Get recent leads."""
    try:
        leads = LeadRecord.list_all(limit=limit)
        return {
            "success": True,
            "leads": leads,
            "count": len(leads),
        }
    except Exception as exc:
        logger.error("Dashboard leads error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/dashboard/appointments")
async def dashboard_appointments(
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """Get recent appointments."""
    try:
        appointments = AppointmentRecord.list_all(limit=limit)
        return {
            "success": True,
            "appointments": appointments,
            "count": len(appointments),
        }
    except Exception as exc:
        logger.error("Dashboard appointments error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/dashboard/daily-report")
async def dashboard_daily_report() -> dict[str, Any]:
    """Get today's daily report."""
    try:
        analytics = AnalyticsHandler()
        report = await analytics.generate_daily_report()
        return {
            "success": True,
            "report": report,
        }
    except Exception as exc:
        logger.error("Daily report error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/dashboard/settings")
async def dashboard_settings() -> dict[str, Any]:
    """Get dashboard configuration settings."""
    try:
        return {
            "success": True,
            "settings": settings.to_dict(),
        }
    except Exception as exc:
        logger.error("Dashboard settings error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
