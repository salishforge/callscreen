# Contributing to CallScreen

CallScreen is open source and welcomes contributions. This guide covers the development workflow.

## Getting Started

1. Fork the repository and clone your fork
2. Install Python 3.12+ and set up the backend:

```bash
cd backend
pip install -e ".[dev,messaging]"
```

3. Copy the environment template:

```bash
cp docker/.env.example docker/.env
```

4. Run the test suite to verify your setup:

```bash
cd backend
python -m pytest tests/ -v
```

## Development Workflow

1. Create a branch from `main` for your change
2. Write tests for new functionality
3. Run the full test suite before submitting
4. Open a pull request with a clear description

## Code Standards

- **Python 3.12+** with type hints throughout
- **Pydantic v2** for all request/response schemas
- **SQLAlchemy 2.0** async patterns for database access
- **pytest** with `@pytest.mark.unit` / `@pytest.mark.integration` markers
- All TwiML output is sanitized via `sanitize_for_twiml()` to prevent injection
- Phone numbers use E.164 format (`+15551234567`)
- SIP URIs use the `sip:` scheme prefix

## Architecture Notes

### Call State Machine
Calls follow a strict state machine (`core/call_state.py`) with transitions enforced in Redis. New states or transitions require updating `ALLOWED_TRANSITIONS`.

### Forwarding Resolution
Forwarding destinations resolve in priority order:
1. Per-user `UserSettings` (database)
2. App-level environment variables (`CALLSCREEN_FORWARD_*`)
3. `TWILIO_PHONE_NUMBER` (backward-compatible fallback)

Emergency callbacks always use PSTN (never SIP) for reliability.

### Webhook Security
All Twilio webhook endpoints validate request signatures using `X-Twilio-Signature`. The fallback endpoint (`/voice/fallback`) intentionally skips validation so it always works even if the application is partially down.

## Running with Docker

```bash
cd docker
docker compose up -d
```

After code changes to the backend, rebuild:

```bash
docker compose build backend
docker compose up -d backend
```

## Reporting Issues

Open a GitHub issue with:
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (redact any credentials)
