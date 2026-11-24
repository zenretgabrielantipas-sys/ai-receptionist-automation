# AI Receptionist Automation

A production-ready AI voice receptionist that answers calls, screens callers, books appointments, captures leads, and sends notifications — all driven by real tools: **VAPI/Retell AI**, **n8n**, **Google Calendar**, **Airtable**, **Twilio**, **SendGrid**, **Slack**, and **Mixpanel**.

This repository contains the complete Python backend (FastAPI) and an `n8n` workflow definition that mirrors the workflow diagram exactly.

## Architecture (matches the HTML workflow diagram)

```
CALLER → AI RECEPTIONIST (VAPI/Retell)
              ↓
      CALL SCREENING (Intent Gateway)
              ↓
   ┌────────┴─────────┴────────┐
   │                           │
APPOINTMENT AGENT      FAQ AGENT      LEAD INTAKE AGENT
      │                           │
APPOINTMENT SCHEDULER    CRM & LEAD DATABASE
(Google Calendar)         (Airtable)
      │                           │
   SMS & EMAIL NOTIFIER     SLACK ALERT AGENT
   (Twilio SMS · SendGrid)   (Slack Webhook)
              │                           │
             DATA ANALYST AGENT ←────────┘
   (Google Sheets · Mixpanel · Weekly report)
```

## Quick Start

### 1. Install dependencies

```bash
cd /home/xee/free-claude-code/receptionist_automation

# Using uv (recommended, see CLAUDE.md)
uv python install 3.14
uv venv
source .venv/bin/activate

# Install packages
uv pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp config/.env.example .env
# Edit .env with your actual API keys
```

Required environment variables at minimum:
- `NVIDIA_NIM_API_KEY` (for the VAPI vision/model calls)
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- `VAPI_API_KEY`, `VAPI_ASSISTANT_ID`
- `N8N_WEBHOOK_URL`
- `SLACK_WEBHOOK_URL`

Optional (enable specific features):
- `GOOGLE_CALENDAR_ID` + Google OAuth credentials → appointment booking
- `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID` → CRM lead storage
- `SENDGRID_API_KEY` or `RESEND_API_KEY` → email confirmations
- `MIXPANEL_API_KEY` → call analytics

### 3. Run the server

```bash
uv run python src/main.py
```

The FastAPI app will start on `http://0.0.0.0:8000`.

### 4. Configure webhooks

Point your provider webhooks to these endpoints:

| Provider | Webhook URL | Purpose |
|----------|-------------|---------|
| VAPI | `https://your-domain.com/webhooks/vapi/call-start` | Incoming call |
| VAPI | `https://your-domain.com/webhooks/vapi/intent` | Intent routing |
| VAPI | `https://your-domain.com/webhooks/vapi/function-call` | Function execution (book, lead, check) |
| VAPI | `https://your-domain.com/webhooks/vapi/call-end` | Call finalization |
| Twilio | `https://your-domain.com/webhooks/twilio/sms-status` | SMS delivery status |
| Slack | `https://your-domain.com/webhooks/slack/command` | Slack slash commands |

### 5. Import n8n workflow

1. Open your n8n instance
2. Click **Import** → **From JSON**
3. Paste the contents of `n8n_workflow.json`
4. Configure credentials for: HTTP Request nodes (Google Calendar, Airtable, Twilio, SendGrid, Slack, Mixpanel)
5. Activate the workflow

## Project Structure

```
receptionist_automation/
├── config/
│   ├── .env.example      # Environment variable template
│   └── settings.py       # Typed settings loader
├── src/
│   └── main.py           # FastAPI webhook server + orchestration logic
├── n8n_workflow.json     # n8n workflow (importable)
└── requirements.txt      # Python dependencies
```

## How the Flow Works

1. **Call comes in** → Twilio routes to VAPI/Retell voice agent
2. **VAPI answers** → Greets caller, listens for intent
3. **Intent detected** → Webhook hits `/webhooks/vapi/intent`
4. **Intent Router** branches to:
   - **Appointment Agent** → checks Google Calendar → books event → SMS/email confirmation → Slack alert
   - **FAQ Agent** → answers from knowledge base → ends call
   - **Lead Intake Agent** → saves to Airtable → Slack alert (urgent)
5. **Call ends** → `/webhooks/vapi/call-end` saves call record + analytics to Mixpanel/Google Sheets
6. **Weekly report** → Data Analyst Agent summarizes call volume, conversion rate, KPI alerts

## Safety & Fail-safes

- **PyAutoGUI FAILSAFE**: Move mouse to top-left corner to abort any desktop automation
- **Calendar failures**: If Google Calendar is unreachable, the agent offers to take details rather than fake a booking
- **CRM failures**: Lead data is logged locally even if Airtable write fails
- **Missing credentials**: Graceful degradation — unconfigured services are skipped with a log warning

## License

MIT
