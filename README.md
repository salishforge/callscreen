# CallScreen

AI-powered call screening for landlines. Built to protect elderly users from spam, scams, and robocalls while ensuring legitimate callers always get through.

CallScreen sits between your phone number (via Twilio) and your actual phone. Incoming calls are triaged against a whitelist/blocklist, unknown callers are screened, and approved calls are forwarded to your phone, SIP endpoint, or multiple devices simultaneously.

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
2. **CallScreen intercepts** every call and checks your contact lists
3. **Known callers** ring through immediately; blocked callers get rejected
4. **Unknown callers** hear a screening prompt and press 1 to connect or 2 to leave a message
5. **Approved calls forward** to your real phone number, SIP endpoint (UniFi Talk, FreePBX), or ring multiple devices at once

## Features

- **Whitelist/blocklist** with instant triage (zero-delay forwarding for known callers)
- **STIR/SHAKEN attestation** for caller ID verification
- **Configurable forwarding** -- PSTN phone, SIP URI, or simultaneous ring
- **Voicemail** with encrypted recording storage (MinIO/S3)
- **Number intelligence** via Twilio Lookup v2 (carrier, CNAM, line type)
- **Community reporting** for crowdsourced spam detection
- **Trust scoring** combining STIR/SHAKEN, carrier data, and community reports
- **AI persona engine** for conversational call screening (LiteLLM-backed)
- **Multi-channel notifications** -- email, SMS, Telegram, Discord
- **Caretaker mode** with message forking and daily digests
- **Emergency callback passthrough** (911 callbacks always ring through)
- **Quiet hours** with timezone-aware scheduling
- **Real-time WebSocket** media streaming for voice AI
- **MCP server** for tool-use integration with AI assistants

## Quick Start

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

## License

MIT License. See [LICENSE](LICENSE) for details.
