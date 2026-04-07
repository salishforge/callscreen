# CallScreen

> **Alpha -- not yet tested with live calls.** The core architecture, API surface, and test suite are in place but this project has not been validated in a real-world telephony environment. Expect breaking changes, missing edge-case handling, and incomplete integrations. Contributions and issue reports are welcome.

An open-source, self-hosted AI call screening and filtering system that blocks nuisance calls, robocalls, phone scams, and telemarketers before they ever ring your phone. Designed for landlines and VoIP lines -- especially for protecting elderly and vulnerable users who are disproportionately targeted by phone fraud.

CallScreen intercepts incoming calls via Twilio, automatically identifies known contacts, rejects blocked numbers, screens unknown callers with an AI-powered answering service, and forwards approved calls to your real phone, SIP extension, or multiple devices simultaneously.

## Why CallScreen

Millions of unwanted calls reach landlines every day -- spam, scams, spoofed numbers, and aggressive telemarketers. The people most harmed are often the least equipped to deal with them: elderly parents, grandparents, and anyone who still depends on a landline as their primary phone.

Existing solutions (carrier-level blocking, Nomorobo, call-blocking devices) catch some robocalls but miss live-caller scams, spoofed local numbers, and social engineering attacks. CallScreen takes a different approach:

- **Intercept everything.** Every call passes through screening before reaching the phone.
- **Whitelist the people who matter.** Known contacts ring through instantly with zero delay.
- **Screen the rest.** Unknown callers hear an automated greeting and must press a button or speak to a live AI to prove they're human and state their purpose.
- **Block the bad actors.** Blocked numbers, community-reported spam, and low-trust callers are silently rejected.
- **Notify the caretaker.** Family members or caregivers get real-time alerts and daily digests about who called, what they wanted, and whether anything needs attention.

The result: the phone only rings for calls that should ring.

## How It Works

```
Incoming Call → Twilio → CallScreen → Triage
                                        ├── Whitelist → Forward to phone
                                        ├── Blocklist → Reject
                                        └── Unknown → Screen (DTMF / AI)
                                                        ├── Press 1 → Forward
                                                        └── Press 2 → Voicemail
```

1. **Port your number** (or set up call forwarding) to a Twilio phone number
2. **CallScreen intercepts** every incoming call and checks your contact lists
3. **Known callers** ring through immediately; blocked callers get rejected
4. **Unknown callers** hear a screening prompt and press 1 to connect or 2 to leave a message
5. **Approved calls forward** to your real phone number, SIP endpoint (UniFi Talk, FreePBX), or ring multiple devices at once

## Features

### Call Filtering and Blocking
- **Whitelist/blocklist** with instant triage -- zero-delay forwarding for known contacts
- **STIR/SHAKEN attestation** for caller ID verification and spoof detection
- **Number intelligence** via Twilio Lookup v2 -- carrier name, CNAM, line type (mobile/landline/VoIP)
- **Community spam reporting** -- crowdsourced database of known scam and nuisance numbers
- **Composite trust scoring** combining STIR/SHAKEN, carrier data, call patterns, and community reports
- **Emergency callback passthrough** -- 911 and emergency service callbacks always ring through immediately

### AI-Powered Answering and Screening
- **AI voice screening** -- conversational agent answers unknown calls, asks the caller's name and purpose, and decides whether to connect or take a message
- **Customizable AI personas** -- configure the screening agent's personality and strictness level
- **LLM-backed intent classification** -- uses Claude, GPT, or any LiteLLM-compatible model to assess caller intent
- **Speech-to-text and text-to-speech** -- real-time voice pipeline with Deepgram STT and ElevenLabs TTS
- **DTMF fallback** -- callers can always press 1 to connect or 2 for voicemail, even without AI screening

### Call Forwarding and Routing
- **Configurable forwarding** -- forward approved calls to a PSTN phone number, SIP URI, or multiple endpoints
- **SIP integration** -- direct forwarding to VoIP systems (UniFi Talk, FreePBX, Asterisk, any SIP PBX)
- **Simultaneous ring** -- ring your cell phone, desk phone, and SIP extension at once; first pickup wins
- **Per-user settings** -- each protected user can have their own forwarding rules, greeting, and screening strictness
- **Quiet hours** -- timezone-aware scheduling to suppress non-emergency calls overnight

### Notifications and Caretaker Support
- **Multi-channel notifications** -- call alerts via email, SMS, Telegram, or Discord
- **Caretaker mode** -- forward call summaries and voicemail transcripts to a family member or caregiver
- **Daily digests** -- scheduled summary of all calls, screened callers, and blocked attempts
- **Voicemail** with encrypted recording storage and background transcription

### Self-Hosted and Extensible
- **Fully self-hosted** -- runs on your own server, no third-party call data collection
- **Docker Compose deployment** -- single command to start all 6 services
- **REST API** with JWT authentication and role-based access control
- **Real-time WebSocket** media streaming for voice AI integration
- **MCP server** for tool-use integration with AI assistants (Claude Desktop, etc.)

## Quick Start

> **Status: Alpha.** The steps below will deploy CallScreen, but live telephony integration has not yet been validated end-to-end. Start with a Twilio trial account for testing.

### Prerequisites

- Docker & Docker Compose
- A [Twilio account](https://www.twilio.com/) with a phone number
- A domain with HTTPS (for Twilio webhooks)

### 1. Clone and configure

```bash
git clone https://github.com/salishforge/callscreen.git
cd callscreen
cp docker/.env.example docker/.env
```

Edit `docker/.env` with your Twilio credentials and forwarding destination. See the [Forwarding Configuration](#forwarding-configuration) section for setup scenarios.

### 2. Start services

```bash
cd docker
docker compose up -d
```

This starts 6 services: backend (FastAPI), celery-worker, celery-beat, PostgreSQL, Redis, and MinIO.

### 3. Configure Twilio webhooks

Point your Twilio phone number's webhooks to your domain:

| Webhook | URL | Method |
|---------|-----|--------|
| Voice Incoming | `https://your-domain.com/api/v1/webhooks/voice/incoming` | POST |
| Voice Fallback | `https://your-domain.com/api/v1/webhooks/voice/fallback` | POST |
| Status Callback | `https://your-domain.com/api/v1/webhooks/voice/status` | POST |

### 4. Verify

```bash
curl https://your-domain.com/ready
# {"status":"ok","version":"0.1.0","database":"ok","redis":"ok"}
```

## Forwarding Configuration

CallScreen supports three forwarding modes, configurable per-user via the API or globally via environment variables.

### Scenario A: Ported Number + Private Line

Port your public number to Twilio. CallScreen screens calls and forwards approved ones to your private (unpublished) number.

```env
CALLSCREEN_FORWARD_NUMBER=+15551234567
```

### Scenario B: SIP / VoIP (UniFi Talk, FreePBX, Asterisk)

Forward calls directly to a SIP endpoint. Requires your PBX to be reachable from Twilio (public IP, VPN, or Twilio SIP Domain).

```env
CALLSCREEN_FORWARD_SIP_URI=sip:100@your-pbx.example.com
```

### Scenario C: Simultaneous Ring

Ring your cell phone, desk phone, and SIP extension at the same time. First device to pick up wins.

```env
CALLSCREEN_FORWARD_NUMBER=+15551234567
CALLSCREEN_SIMULTANEOUS_RING=+15559876543,+15558765432
CALLSCREEN_FORWARD_SIP_URI=sip:100@your-pbx.example.com
```

### Per-User Configuration (API)

Each user can override the global forwarding config:

```bash
curl -X PUT https://your-domain.com/api/v1/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "forward_mode": "simultaneous",
    "forward_phone_number": "+15551234567",
    "forward_sip_uri": "sip:100@pbx.local",
    "simultaneous_ring_numbers": "+15559876543",
    "forward_timeout": 30
  }'
```

| Mode | Behavior |
|------|----------|
| `phone` | Forward to a single PSTN number |
| `sip` | Forward to a SIP URI |
| `simultaneous` | Ring all configured endpoints at once |

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────┐
│   Twilio     │────▶│  FastAPI Backend (port 8000)          │
│   Webhooks   │◀────│  ├── /api/v1/webhooks/voice/*        │
└─────────────┘     │  ├── /api/v1/{auth,contacts,calls}   │
                    │  ├── /api/v1/settings                 │
                    │  └── /ws/media-stream                 │
                    └──────┬────────────┬──────────────────┘
                           │            │
                    ┌──────▼──┐  ┌──────▼──────┐
                    │ Postgres │  │    Redis     │
                    │ (data)   │  │ (call state, │
                    └──────────┘  │  sessions)   │
                                  └──────────────┘
                    ┌─────────────────────────────┐
                    │  Celery Workers              │
                    │  ├── Recording processing    │
                    │  ├── Number intelligence     │
                    │  └── Daily digest scheduler  │
                    └─────────────────────────────┘
                    ┌─────────────────────────────┐
                    │  MinIO (S3-compatible)       │
                    │  └── Encrypted recordings    │
                    └─────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16, Redis 7 |
| Task Queue | Celery with Redis broker |
| Telephony | Twilio Voice, TwiML, Lookup v2 |
| AI | LiteLLM (Anthropic Claude, OpenAI), Deepgram STT, ElevenLabs TTS |
| Storage | MinIO / S3 with AES-256-GCM encryption |
| Auth | JWT (access + refresh), bcrypt, RBAC (admin/caretaker/user) |
| Deployment | Docker Compose, nginx reverse proxy |

## API Documentation

When running in development mode, interactive API docs are available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development

### Running Tests

```bash
cd backend
pip install -e ".[dev]"
python -m pytest tests/ -v
```

444 tests covering TwiML generation, call state machine, forwarding logic, intelligence scoring, AI personas, messaging adapters, and security validators.

### Project Structure

```
backend/
  src/callscreen/
    api/v1/          # REST endpoints (auth, contacts, calls, settings, webhooks)
    api/ws/          # WebSocket media stream
    ai/              # LLM integration, persona engine, screening prompts
    core/            # Call state machine, TwiML builders, recording, screening
    intelligence/    # Trust scoring, STIR/SHAKEN, Twilio Lookup, community reports
    messaging/       # Multi-channel delivery (email, SMS, Telegram, Discord)
    models/          # SQLAlchemy models
    schemas/         # Pydantic request/response schemas
    security/        # Auth, CORS, CSP, input validation, Twilio signature verification
    voice/           # STT/TTS providers, audio conversion, session management
    tasks/           # Celery tasks and scheduled jobs
    mcp/             # Model Context Protocol server
  tests/
    unit/            # 400+ unit tests
    integration/     # API integration tests
docker/
  docker-compose.yml      # Development stack (6 services)
  docker-compose.prod.yml # Production with Traefik
  Dockerfile.backend
  Dockerfile.celery
  Dockerfile.frontend
  .env.example
```

## Project Status

This is an **alpha-stage** project. The following is implemented and unit-tested but not yet validated with live telephony:

| Component | Status |
|-----------|--------|
| Call triage (whitelist/blocklist/screen) | Built, unit-tested |
| TwiML generation and webhook handlers | Built, unit-tested |
| Configurable forwarding (phone/SIP/simultaneous) | Built, unit-tested |
| Number intelligence and trust scoring | Built, unit-tested |
| AI persona screening engine | Built, unit-tested |
| Voice pipeline (STT/TTS/WebSocket) | Built, unit-tested |
| Multi-channel messaging and notifications | Built, unit-tested |
| Caretaker forking and daily digests | Built, unit-tested |
| Docker Compose deployment | Built, runs locally |
| End-to-end live call testing | **Not yet done** |
| Frontend dashboard | Scaffold only |
| Alembic database migrations | Not yet generated |
| Production hardening and load testing | Not yet done |

Contributions, testing, and feedback are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License. See [LICENSE](LICENSE) for details.
