# The Memory Host 🧠🎙️

A **voice-based memory card game** powered by [Pipecat](https://github.com/pipecat-ai/pipecat). A bot acts as a game show host — it speaks sequences of words, and you repeat them back from memory. Each correct round adds a new word. How many can you remember?

## Features

- 🎙️ **Voice-powered** — speak your answers using your microphone
- 🤖 **Bot game host** — pre-written prompt templates (no LLM needed)
- 📈 **10 progressive rounds** — from 3 words up to 12
- 🏆 **Leaderboard** — tracks best scores across games
- ⚡ **Real-time WebRTC** — low-latency audio via SmallWebRTC
- 🛡️ **Double-scoring prevention** — three-layer protection (in-memory, DB constraint, app-level check)
- 🎨 **Dark mode UI** — glass morphism design with Tailwind CSS

## Quick Start

### Prerequisites

- Python 3.14+
- Node.js 20+
- Docker (for PostgreSQL)
- A [Deepgram API key](https://console.deepgram.com/) (free tier available)

### 1. Clone & Environment Setup

```bash
git clone https://github.com/CpBruceMeena/the-memory-host.git
cd the-memory-host

# Copy environment config
cp .env.example .env
# Edit .env and paste your DEEPGRAM_API_KEY
```

### 2. Backend Setup

```bash
cd backend

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL
cd ..
docker compose up -d postgres

# Start the backend
./run.sh backend
```

The backend starts at `http://localhost:8000`. API docs are at `http://localhost:8000/docs`.

### 3. Frontend Setup

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend starts at `http://localhost:3000`.

### 4. Play!

Open `http://localhost:3000`, enter your name, and click **Start Game**.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js 15)                     │
│  ┌──────────┐  ┌────────────────┐  ┌──────────────────────┐ │
│  │ Landing  │  │  Game Room     │  │ Leaderboard          │ │
│  └────┬─────┘  └───────┬────────┘  └─────────┬────────────┘ │
│       │                │                     │               │
│       └────────┬───────┘                     │               │
│                │                             │               │
│         ┌──────▼──────┐                     │               │
│         │  BFF Routes  │─────────────────────┘               │
│         └──────┬──────┘                                      │
└────────────────┼─────────────────────────────────────────────┘
                 │ HTTP/JSON
    ┌────────────┼─────────────────────────────────┐
    │            │                                 │
    │   ┌────────▼────────┐    ┌──────────────────┐│
    │   │  FastAPI Backend │    │ Signaling Server ││
    │   │  (Python)        │    │ (WebSocket)      ││
    │   │                  │    └────────┬─────────┘│
    │   │  • Game Engine   │             │          │
    │   │  • Voice Bot     │    SmallWebRTC P2P     │
    │   │  • REST APIs     │    Audio Channel        │
    │   └────────┬────────┘             │           │
    │            │                      │           │
    │   ┌────────▼────────┐             │           │
    │   │  PostgreSQL     │             │           │
    │   └─────────────────┘             │           │
    │                                   ▼           │
    │  ┌──────────────────────────────────────────┐ │
    │  │        PIPECAT VOICE BOT                 │ │
    │  │  WebRTC → Deepgram STT → GameProcessor  │ │
    │  │           → Deepgram TTS → WebRTC        │ │
    │  └──────────────────────────────────────────┘ │
    └───────────────────────────────────────────────┘
```

### Project Structure

```
the-memory-host/
├── backend/
│   ├── app/                          # Main application package
│   │   ├── api/                      # FastAPI layer
│   │   │   ├── main.py               # App entrypoint
│   │   │   ├── routes.py             # Session & leaderboard endpoints
│   │   │   ├── deps.py               # Dependency injection
│   │   │   └── schemas.py            # Pydantic request/response models
│   │   ├── core/                     # Infrastructure
│   │   │   ├── config.py             # Environment config (pydantic-settings)
│   │   │   ├── cache.py              # In-memory TTLCache
│   │   │   └── constants.py          # Application constants (word pool)
│   │   ├── services/                 # Business logic
│   │   │   ├── game_state.py         # State machine enum + dataclass
│   │   │   ├── game_logic.py         # Sequence generation, validation
│   │   │   ├── game_processor.py     # Pipecat FrameProcessor (game engine)
│   │   │   ├── prompt_templates.py   # Categorized dialog templates
│   │   │   └── bot.py                # Pipecat pipeline assembly
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── base.py               # Declarative Base + mixins
│   │   │   ├── session.py            # Game session model
│   │   │   └── round.py              # Round model
│   │   └── db/
│   │       └── database.py           # AsyncSession + engine setup
│   ├── tests/                        # Unit tests
│   └── requirements.txt
│
├── frontend/                         # Next.js 15 (App Router)
│   ├── app/
│   │   ├── page.tsx                  # Landing page (start game)
│   │   ├── layout.tsx                # Root layout + nav
│   │   ├── loading.tsx               # Loading state
│   │   ├── globals.css               # Tailwind + custom styles
│   │   ├── game/[sessionId]/         # Game room page
│   │   ├── leaderboard/              # Leaderboard page
│   │   └── api/                      # BFF API routes
│   ├── components/
│   │   ├── GameHeader.tsx            # Score + round + status
│   │   ├── WebRTCRoom.tsx            # WebRTC audio (SSR-safe)
│   │   ├── GameLog.tsx               # Round history
│   │   ├── GameOverModal.tsx         # End-game stats + replay
│   │   ├── LeaderboardTable.tsx      # Ranked scores
│   │   ├── PlayerNameForm.tsx        # Name input form
│   │   └── LoadingSkeleton.tsx       # Loading states
│   ├── hooks/
│   │   ├── useGameState.ts           # 2s polling hook
│   │   └── useLeaderboard.ts         # Fetch + auto-refresh
│   └── lib/
│       └── api.ts                    # API client (server-side)
│
├── scripts/
│   └── init_db.sql                   # Database schema (PostgreSQL)
├── docker-compose.yml                # PostgreSQL only (backend runs via venv)
├── run.sh                            # Start db / backend / frontend
├── .env.example                      # Environment template
└── pyproject.toml
```

---

## Game Flow

```
IDLE → START_GAME → SPEAK_SEQUENCE → LISTEN → VALIDATE
                    ↑                           │
                    │                   ┌───────┴───────┐
                    │              CORRECT         INCORRECT
                    │                   │               │
                    └─── ROUND_PASS ←──┘         GAME_OVER → ENDED
```

| Round | Words | Difficulty |
|-------|-------|-----------|
| 1 | 3 | Easy |
| 2 | 4 | Easy |
| 3 | 5 | Medium |
| 4 | 6 | Medium |
| 5 | 7 | Hard |
| ... | ... | ... |
| 10 | 12 | Grandmaster |

The bot speaks a sequence, you repeat it back. Correct? +1 word added. Wrong? Game over with your score.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sessions` | Create a new game session |
| `GET` | `/api/sessions/{id}` | Get game state (score, round, status) |
| `POST` | `/api/sessions/{id}/end` | End a session manually |
| `GET` | `/api/leaderboard` | Top player scores |
| `GET` | `/api/health` | Health check |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPGRAM_API_KEY` | ✅ | — | Deepgram API key for STT (Nova-2) & TTS (Aura) |
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://postgres:password@localhost:5432/the-memory-host` | PostgreSQL connection |
| `SMALLWEBRTC_SERVER_URL` | ❌ | `http://localhost:3001` | WebRTC signaling server |
| `BOT_NAME` | ❌ | `Memory Game Host` | Bot display name |
| `MAX_ROUNDS` | ❌ | `10` | Maximum game rounds |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level |
| `NEXT_PUBLIC_BACKEND_URL` | ❌ | `http://localhost:8000` | Backend URL (frontend) |

---

## Configuration Reference

The `backend/app/core/config.py` exposes all configuration via `pydantic-settings`. All values can be set via environment variables or a `.env` file at the project root.

### Cache Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_ACTIVE_SESSION_TTL` | `1800` | Session cache TTL (30 min) |
| `CACHE_MAX_ACTIVE_SESSIONS` | `100` | Max cached sessions |
| `CACHE_LEADERBOARD_TTL` | `60` | Leaderboard cache TTL (1 min) |
| `CACHE_ROUND_TTL` | `1800` | Round state cache TTL (30 min) |

---

## Running Tests

```bash
cd backend
source .venv/bin/activate

# Run all tests
pytest

# Run specific test file (once written — see TASK_LIST.md)
pytest tests/test_game_logic.py -v
```

> **Note:** Unit tests are planned in Phase 5 of the development roadmap. See `TASK_LIST.md` for details.

---

## Deployment

### Production WebRTC (Daily.co)

For production, swap the WebRTC transport from `SmallWebRTCTransport` to `DailyTransport`:

```python
# backend/app/services/bot.py
from pipecat.transports.daily import DailyTransport

transport = DailyTransport(
    room_url=daily_room_url,
    token=daily_token,
    bot_name="Memory Game Host",
)
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Voice Pipeline | [Pipecat](https://github.com/pipecat-ai/pipecat) |
| WebRTC | SmallWebRTC (built into Pipecat) |
| STT / TTS | [Deepgram](https://deepgram.com) Nova-2 / Aura |
| Backend API | [FastAPI](https://fastapi.tiangolo.com/) (Python) |
| Database | [PostgreSQL](https://www.postgresql.org/) 16 |
| ORM | [SQLAlchemy](https://www.sqlalchemy.org/) 2.0 (async) |
| Frontend | [Next.js](https://nextjs.org/) 15 (App Router) |
| Styling | [Tailwind CSS](https://tailwindcss.com/) v3 |
| Audio Player | WebRTC API (browser native) |

---

## License

MIT
