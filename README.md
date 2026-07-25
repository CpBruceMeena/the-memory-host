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
# Start all services (REST API + Game Engine + Frontend)
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

## Running the Project

```bash
# Start all services (REST API + Game Engine + Frontend)
./run.sh

# Start individual services
./run.sh rest-api       # Port 8000
./run.sh game-engine    # Port 3002 (signaling on 3001)
./run.sh frontend       # Port 3000
```

---

## Tech Stack

| Component | Technology |
|--------|--------|
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
