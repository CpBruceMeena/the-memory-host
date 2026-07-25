# The Memory Host 🧠🎙️

A **voice-based memory card game** powered by [Pipecat](https://github.com/pipecat-ai/pipecat). A bot acts as a game show host — it speaks sequences of words, and you repeat them back from memory. Each correct round adds a new word. How many can you remember?

## Features

- 🎙️ **Voice-powered** — speak your answers using your microphone
- 🤖 **Bot game host** — pre-written prompt templates (no LLM needed)
- 📈 **10 progressive rounds** — from 1 word up to 10
- 🏆 **Leaderboard** — top 3 highest-scoring individual sessions
- ⚡ **Real-time WebRTC** — low-latency audio via SmallWebRTC
- 🛡️ **Double-scoring prevention** — three-layer protection (in-memory, DB constraint, app-level check)
- 🎨 **Dark mode UI** — glass morphism design with Tailwind CSS
- 🔄 **Push-to-talk recording** — click-to-start/stop recording button with animated sound wave visualization
- 🇬🇧 **British English voice** — using Deepgram's `aura-2-pandora-en` for natural speech

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

### 2. Start Services

```bash
# Start PostgreSQL
docker compose up -d postgres

# Start all services (rest-api + game-engine + frontend)
./run.sh
```

### 3. Play!

Open `http://localhost:3000`, enter your name, and click **Start Game**.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js 15)                        │
│  Port 3000                                                      │
│  ┌──────────┐  ┌────────────────┐  ┌────────────────────────┐   │
│  │ Landing  │  │  Game Room     │  │ Leaderboard            │   │
│  └────┬─────┘  └───────┬────────┘  └─────────┬──────────────┘   │
│       │                │                     │                  │
│       └────────┬───────┘                     │                  │
│                │                             │                  │
│         ┌──────▼──────┐                     │                  │
│         │  BFF Routes  │─────────────────────┘                  │
│         │  (/api/*)    │                                        │
│         └──────┬──────┘                                         │
└────────────────┼────────────────────────────────────────────────┘
                 │ HTTP/JSON
    ┌────────────┼────────────────────────────────────┐
    │            │                                     │
    │   ┌────────▼────────┐      ┌──────────────────┐  │
    │   │  REST API        │      │  Game Engine     │  │
    │   │  Port 8000       │      │  Port 3002       │  │
    │   │  FastAPI         │◄────►│  FastAPI         │  │
    │   │                  │      │                  │  │
    │   │  • Sessions      │      │  • Signaling     │  │
    │   │  • Leaderboard   │      │    Server (3001) │  │
    │   │  • Health        │      │  • Voice Bot     │  │
    │   └────────┬────────┘      │  • Game Engine   │  │
    │            │               └──────────────────┘  │
    │            │                        │            │
    │   ┌────────▼────────┐               │            │
    │   │  PostgreSQL     │     WebRTC P2P Audio       │
    │   │  (the-memory-   │               │            │
    │   │   host)         │               ▼            │
    │   └─────────────────┘   ┌─────────────────────┐  │
    │                         │   PIPECAT BOT       │  │
    │                         │ WebRTC → STT →     │  │
    │                         │ GameProcessor →    │  │
    │                         │ TTS → WebRTC       │  │
    │                         └─────────────────────┘  │
    └───────────────────────────────────────────────────┘
```

### Project Structure

```
the-memory-host/
├── backend/
│   ├── rest-api/                     # REST API service (port 8000)
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── main.py           # FastAPI entrypoint
│   │   │   │   ├── routes.py         # Session & leaderboard endpoints
│   │   │   │   ├── deps.py           # Dependency injection (DB session)
│   │   │   │   └── schemas.py        # Pydantic request/response models
│   │   │   ├── core/
│   │   │   │   ├── config.py         # Environment config
│   │   │   │   └── constants.py      # Application constants
│   │   │   ├── models/
│   │   │   │   ├── base.py           # SQLAlchemy Base + mixins
│   │   │   │   ├── session.py        # Session model
│   │   │   │   └── round.py          # Round model
│   │   │   └── db/
│   │   │       └── database.py       # AsyncSession + engine
│   │   └── requirements.txt
│   │
│   ├── game-engine/                  # Game Engine service (port 3002)
│   │   ├── app/
│   │   │   ├── main.py               # FastAPI entrypoint + signaling (port 3001)
│   │   │   ├── signaling/
│   │   │   │   └── server.py         # WebSocket signaling server
│   │   │   ├── services/
│   │   │   │   ├── bot.py            # Pipecat pipeline assembly + CLI
│   │   │   │   ├── game_processor.py # Pipecat FrameProcessor (game engine)
│   │   │   │   ├── game_state.py     # State machine enum + GameData dataclass
│   │   │   │   ├── game_logic.py     # Sequence generation, word-by-word comparison
│   │   │   │   ├── prompt_templates.py  # Categorized dialog templates
│   │   │   │   └── custom_tts.py     # Slower TTSService with speed control
│   │   │   ├── models/               # Shared SQLAlchemy models
│   │   │   ├── core/                 # Cache, config
│   │   │   └── db/                   # Database session
│   │   └── requirements.txt
│   │
│   ├── scripts/
│   │   └── init_db.sql               # Database schema
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
│   │   ├── WebRTCRoom.tsx            # WebRTC audio + recording controls
│   │   ├── GameLog.tsx               # Round history
│   │   ├── RoundHistory.tsx          # Polling round history fetcher
│   │   ├── GameOverModal.tsx         # End-game stats + replay
│   │   ├── LeaderboardTable.tsx      # Top 3 ranked sessions
│   │   ├── PlayerNameForm.tsx        # Name input form
│   │   └── LoadingSkeleton.tsx       # Loading states
│   ├── hooks/
│   │   ├── useGameState.ts           # Polling hook (2s interval)
│   │   └── useLeaderboard.ts         # Fetch + auto-refresh
│   └── lib/
│       └── api.ts                    # API client (server-side)
│
├── docs/
│   └── sequence-diagram.svg          # Game flow sequence diagram
├── scripts/
│   └── init_db.sql
├── docker-compose.yml                # PostgreSQL only
├── run.sh                            # Start all services
├── .env.example
└── pyproject.toml
```

---

## Game Flow

### State Machine

```
IDLE → START_GAME → SPEAK_SEQUENCE → LISTEN → VALIDATE
                    ↑                            │
                    │                    ┌───────┴──────────┐
                    │              PERFECT             PARTIAL
                    │                   │                   │
                    └─── ROUND_PASS ◄───┘         RETRY ◄───┘
                                                      │
                                              GAME_OVER → ENDED
```

### Round Progression

| Round | Words | Difficulty |
|-------|-------|-----------|
| 1 | 1 | Beginner |
| 2 | 2 | Beginner |
| 3 | 3 | Easy |
| 4 | 4 | Easy |
| 5 | 5 | Medium |
| 6 | 6 | Medium |
| 7 | 7 | Hard |
| 8 | 8 | Hard |
| 9 | 9 | Expert |
| 10 | 10 | Grandmaster |

**Max rounds:** 10 (configurable via `MAX_ROUNDS`)
**Retries per round:** 3 (configurable via `max_retries_per_round`)
**Scoring:** Word-by-word match — each correctly remembered word awards 1 point
**Word pool:** 100+ common words (animals, fruits, objects, nature)

### Game Loop

1. **Bot speaks** each word individually with 1-second pauses (`"Word 1: apple. Word 2: banana."`)
2. **User taps Start Recording**, speaks the words back
3. **User taps Stop Recording**, signal is sent to bot for validation
4. **Bot compares** user's words vs expected (word-by-word, partial scoring)
5. **If perfect** → move to next round with +1 word added
6. **If partial with retries left** → re-announce words, user tries again (up to 3 retries)
7. **If no retries left** → Game Over, pipeline stops, session saved to DB

---

## API Endpoints

### REST API (Port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sessions` | Create a new game session |
| `GET` | `/api/sessions/{id}` | Get game state (score, round, status) |
| `POST` | `/api/sessions/{id}/end` | End a session manually |
| `GET` | `/api/sessions/{id}/rounds` | Get round history for a session |
| `GET` | `/api/leaderboard` | Top 3 highest-scoring individual sessions |
| `GET` | `/api/health` | Health check |

### Game Engine (Port 3002)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/start-session` | Start a Pipecat voice bot for a session |
| `GET` | `/health` | Health check |

### Signaling (Port 3001 — WebSocket)

| Message Type | Direction | Description |
|-------------|-----------|-------------|
| `join` | Client → Server | Register as peer (bot or receiver) |
| `offer` | Client → Bot | SDP offer from receiving client |
| `answer` | Bot → Client | SDP answer from bot |
| `ice-candidate` | Bidirectional | ICE candidate relay |
| `user_done` | Client → Bot | Push-to-talk released signal |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPGRAM_API_KEY` | ✅ | — | Deepgram API key for STT (Nova-2) & TTS (Aura 2) |
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://postgres:password@localhost:5432/the-memory-host` | PostgreSQL connection |
| `SMALLWEBRTC_SERVER_URL` | ❌ | `http://localhost:3001` | WebRTC signaling server |
| `BOT_NAME` | ❌ | `Memory Game Host` | Bot display name |
| `MAX_ROUNDS` | ❌ | `10` | Maximum game rounds |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level |
| `GAME_ENGINE_URL` | ❌ | `http://localhost:3002` | Game engine URL (REST API → Game Engine) |

---

## Configuration Reference

### Cache Settings (`backend/rest-api/app/core/config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_ACTIVE_SESSION_TTL` | `1800` | Session cache TTL (30 min) |
| `CACHE_MAX_ACTIVE_SESSIONS` | `100` | Max cached sessions |
| `CACHE_LEADERBOARD_TTL` | `60` | Leaderboard cache TTL (1 min) |
| `CACHE_ROUND_TTL` | `1800` | Round state cache TTL (30 min) |

### TTS Voice (`backend/game-engine/app/services/bot.py`)

Currently using **`aura-2-pandora-en`** (British English, feminine) — the closest available accent to Indian English in Deepgram's Aura 2 lineup. Speed is set to **0.9** (10% slower).

---

## Running the Project

```bash
# Start all services (REST API + Game Engine + Frontend)
./run.sh

# Start individual services
./run.sh rest-api       # Port 8000
./run.sh game-engine    # Port 3002 (signaling on 3001)
./run.sh frontend       # Port 3000
```

Logs are written to both stdout and `app.log` at the project root.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Voice Pipeline | [Pipecat](https://github.com/pipecat-ai/pipecat) |
| WebRTC | SmallWebRTC (built into Pipecat) |
| STT | [Deepgram](https://deepgram.com) Nova-2 |
| TTS | [Deepgram](https://deepgram.com) Aura 2 (`aura-2-pandora-en`) |
| REST API | [FastAPI](https://fastapi.tiangolo.com/) (Python) |
| Database | [PostgreSQL](https://www.postgresql.org/) 16 |
| ORM | [SQLAlchemy](https://www.sqlalchemy.org/) 2.0 (async) |
| Frontend | [Next.js](https://nextjs.org/) 15 (App Router) |
| Styling | [Tailwind CSS](https://tailwindcss.com/) v3 |
| Audio Player | WebRTC API (browser native) |

---

## License

MIT
