# The Memory Host — Architecture & Implementation Plan

> **Framework:** Pipecat (Python)
> **Frontend:** Next.js (TypeScript)
> **Transport:** SmallWebRTC (Daily.co for production)
> **STT/TTS:** Deepgram (Nova-2 / Aura)
> **LLM:** Removed — using pre-written prompt templates with random selection
> **Database:** PostgreSQL (`the-memory-host`)
> **Cache:** In-memory (TTLCache)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Tech Stack & Justification](#3-tech-stack--justification)
4. [Services Breakdown](#4-services-breakdown)
5. [Game Flow & State Machine](#5-game-flow--state-machine)
6. [Database Schema](#6-database-schema)
7. [Caching Strategy](#7-caching-strategy)
8. [API Endpoints](#8-api-endpoints)
9. [Pipecat Pipeline Design](#9-pipecat-pipeline-design)
10. [MemoryGameProcessor (Core Logic)](#10-memorygameprocessor-core-logic)
11. [Prompt Templates & Random Selection](#11-prompt-templates--random-selection)
12. [Frontend Architecture (Next.js)](#12-frontend-architecture-nextjs)
13. [Interruption Handling](#13-interruption-handling)
14. [Double-Scoring Prevention](#14-double-scoring-prevention)
15. [Project Structure](#15-project-structure)
16. [Implementation Roadmap](#16-implementation-roadmap)
17. [Setup & Environment Variables](#17-setup--environment-variables)

---

## 1. System Overview

We are building a **voice-based Memory Card game** using the [Pipecat](https://github.com/pipecat-ai/pipecat) framework. The bot acts as a game show host:

1. **Bot speaks** a sequence of words to the user
2. **User repeats** the sequence back via voice
3. **Bot evaluates** correctness (pure Python logic — no LLM dependency)
4. **Game progresses** — correct answers add more words each round
5. **Game ends** on wrong answer or max rounds reached

### Key Requirements

- ✅ Pipecat as the core voice pipeline framework
- ✅ SmallWebRTC for WebRTC transport (Daily.co for production)
- ✅ Proper turn-taking (wait for user to finish before evaluating)
- ✅ Clean interruption handling (user interrupts mid-speech → bot recovers)
- ✅ Engaging, human-like game-host behavior using pre-written prompt templates
- ✅ Database persistence (sessions, rounds, responses, scores)
- ✅ Backend APIs for session and score data
- ✅ In-memory cache for active sessions and leaderboard
- ✅ No double-scoring
- ✅ Memory validation in backend code (not LLM-dependent)
- ✅ Next.js frontend for testing and end-to-end flow

---

## 2. Architecture Diagram

### Two-Service Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND SERVICE (Next.js)                           │
│                                                                              │
│  ┌──────────────────┐  ┌─────────────────────┐  ┌────────────────────────┐  │
│  │  Landing /        │  │  Game Room Page     │  │  Leaderboard Page     │  │
│  │  Create Session   │  │  (SmallWebRTC       │  │  (fetch from API)     │  │
│  │                   │  │   video element)    │  │                        │  │
│  └────────┬─────────┘  └────────┬────────────┘  └──────────┬─────────────┘  │
│           │                     │                           │                │
│           └──────────┬──────────┘                           │                │
│                      │                                      │                │
│               ┌──────▼──────┐                               │                │
│               │ Next.js API │                               │                │
│               │ Routes      │                               │                │
│               │ (BFF layer) │                               │                │
│               └──────┬──────┘                               │                │
└──────────────────────┼───────────────────────────────────────┘                │
                       │ HTTP/JSON                                              │
           ┌───────────┼──────────────────────────┐                            │
           │           │                          │                            │
           │  ┌────────▼────────┐    ┌────────────▼────────────┐               │
           │  │  FastAPI        │    │  SmallWebRTC Signal     │               │
           │  │  Backend        │    │  Server (room & token   │               │
           │  │  (Python)       │    │   management)           │               │
           │  │                 │    └────────────┬────────────┘               │
           │  │  • Game Engine  │                 │                            │
           │  │  • Voice Bot    │                 │                            │
           │  │  • REST APIs    │                 │                            │
           │  └────────┬────────┘                 │                            │
           │           │                          │                            │
           │  ┌────────▼────────┐                 │                            │
           │  │  PostgreSQL     │        SmallWebRTC Room (WebRTC bridge)      │
           │  │  (the-memory-   │                 │                            │
           │  │   host)         │                 │                            │
           │  │                 │                 │                            │
           │  │  • sessions     │                 │                            │
           │  │  • rounds       │                 │                            │
           │  │  • leaderboard  │                 │                            │
           │  └─────────────────┘                 │                            │
           │                                      │                            │
           │  ┌───────────────────────────────────┘                            │
           │  │                                                                 │
           │  ▼                                                                 │
           │  ┌─────────────────────────────────────────────────────────────┐   │
           │  │              PIPECAT VOICE BOT (bot.py)                     │   │
           │  │                                                             │   │
           │  │   SmallWebRTCTransport ◄──► Silero VAD + SmartTurn         │   │
           │  │        │                                                    │   │
           │  │        ▼                                                    │   │
           │  │   DeepgramSTTService (user speech → text)                  │   │
           │  │        │                                                    │   │
           │  │        ▼                                                    │   │
           │  │   ContextAggregator (injects prompt templates)              │   │
           │  │        │                                                    │   │
           │  │        ▼                                                    │   │
           │  │   ┌───────────────────────────────────────────────────┐     │   │
           │  │   │  MemoryGameProcessor (Custom FrameProcessor)      │     │   │
           │  │   │  • Game state machine: IDLE → SPEAK → LISTEN →   │     │   │
           │  │   │    VALIDATE → ROUND_PASS / GAME_OVER              │     │   │
           │  │   │  • Generates word sequences per round             │     │   │
           │  │   │  • Validates user responses (pure Python)        │     │   │
           │  │   │  • Prevents double-scoring                       │     │   │
           │  │   │  • Handles interruptions                         │     │   │
           │  │   │  • Selects random prompt templates                │     │   │
           │  │   └───────────────────────────────────────────────────┘     │   │
           │  │        │                                                    │   │
           │  │        ▼                                                    │   │
           │  │   PromptTemplateSelector (random pick from template list)   │   │
           │  │        │                                                    │   │
           │  │        ▼                                                    │   │
           │  │   DeepgramTTSService (text response → speech)              │   │
           │  │        │                                                    │   │
           │  │        ▼                                                    │   │
           │  │   SmallWebRTCTransport (audio out → user)                   │   │
           │  └─────────────────────────────────────────────────────────────┘   │
           └────────────────────────────────────────────────────────────────────┘
```

### High-Level Data Flow

```
┌──────────┐     POST /api/sessions     ┌────────────┐     Create S(We)RTC Room    ┌──────────────┐
│  Next.js  │ ───────────────────────►  │  FastAPI   │ ───────────────────────►   │  SmallWebRTC │
│  Frontend │ ◄───────────────────────  │  Backend   │ ◄───────────────────────   │  Signal API  │
│           │   { room_url, token }    └────────────┘    { url, token }           └──────────────┘
│           │
│           │     SmallWebRTC (WebRTC)
│    ┌──────┴──────┐     (same room)       ┌──────────────┐
│    │ SmallWebRTC │ ◄──────────────────►  │ Pipecat Bot  │
│    │ Client      │                       │ (bot.py)     │
│    └─────────────┘                       └──────────────┘
│           │
│           │     GET /api/sessions/:id  (polling for game state)
│           │ ◄─────────────────────────────────────────►
│           │     GET /api/leaderboard
└──────────┘
```

**Note:** Daily.co is listed as the production WebRTC transport, but for initial development we use [smallwebrtc](https://github.com/paulfioravanti/smallwebrtc) — a lightweight, open-source WebRTC signaling server. Migration to Daily.co in production requires swapping the transport layer only.

---

## 3. Tech Stack & Justification

| Component         | Service              | Free Tier / Cost                  | Why Choose                          |
|-------------------|----------------------|-----------------------------------|-------------------------------------|
| **Voice Pipeline**| Pipecat              | Open-source (MIT)                 | Industry standard for voice AI bots |
| **Transport**     | SmallWebRTC (dev)    | Free / Open-source                | Lightweight WebRTC signaling        |
| **Transport**     | Daily.co (prod)      | 10,000 min/month free             | Production-ready, scalable          |
| **STT**           | Deepgram Nova-2      | $200 free credits (≈43K mins)     | Low latency, high accuracy          |
| **TTS**           | Deepgram Aura        | $200 free credits                 | Natural voices, same provider       |
| **LLM**           | — (removed)          | —                                 | Using pre-written prompt templates  |
| **Database**      | PostgreSQL           | Free (self-hosted)                | Reliable, JSON support              |
| **Cache**         | In-memory (TTLCache) | Free                              | Simple, no infra overhead           |
| **Backend API**   | FastAPI (Python)     | Free                              | Async, fast, great DX               |
| **Frontend**      | Next.js (TypeScript) | Free                              | SSR, API routes, modern React       |

**Deepgram API Key:** A Deepgram API key is required for both STT (Nova-2) and TTS (Aura) services. Generate one at [deepgram.com](https://deepgram.com).

---

## 4. Services Breakdown

### Service 1: Backend (Python — FastAPI + Pipecat)

Single Python service responsible for:

- **Game Engine** — MemoryGameProcessor, word sequence generation, response validation, state machine
- **Voice Bot** — Pipecat pipeline with STT, TTS, turn detection, interruption handling
- **REST APIs** — Session CRUD, leaderboard, health checks
- **Database** — PostgreSQL connection, models, migrations
- **Data Layer** — In-memory cache, DB session management

### Service 2: Frontend (Next.js — TypeScript)

- **Pages** — Landing, Game Room, Leaderboard
- **API Routes (BFF)** — Proxy requests to backend
- **SmallWebRTC Client** — Join WebRTC room, audio/video
- **Game State Polling** — Poll backend for game state updates
- **UI Components** — GameHeader, GameLog, GameOverModal, etc.

---

## 5. Game Flow & State Machine

### State Transitions

```
                         ┌──────────┐
                         │   IDLE   │ ◄── Bot starts, waiting for user to join
                         └────┬─────┘
                              │ User joins room
                              ▼
                    ┌───────────────────┐
                    │  START_GAME       │
                    │  "Welcome to the  │
                    │   memory game!"   │  ← Random template picked
                    └────────┬──────────┘
                             │
                             ▼
                    ┌───────────────────┐
              ┌───► │  SPEAK_SEQUENCE   │  ← Prompt template: round intro
              │     │  Bot says:        │    + game processor injects
              │     │  "Round 1: apple, │    the word sequence
              │     │   banana, cat."   │
              │     └────────┬──────────┘
              │              │ Bot finishes speaking
              │              ▼
              │     ┌───────────────────┐
              │     │     LISTEN        │  ← Wait for user response
              │     │  Microphone open  │    Silero VAD + SmartTurn
              │     │  Collecting words │    detects end of turn
              │     └────────┬──────────┘
              │              │ User stops speaking (turn detected)
              │              ▼
              │     ┌───────────────────┐
              │     │    VALIDATE       │  ← Pure Python comparison
              │     │  Compare user     │    MemoryGameProcessor
              │     │  response vs      │    compares word arrays
              │     │  expected         │
              │     └────────┬──────────┘
              │              │
              │        ┌─────┴─────┐
              │        │           │
              │   CORRECT      INCORRECT
              │        │           │
              │        ▼           ▼
              │  ┌──────────┐  ┌──────────┐
              │  │ROUND_PASS│  │GAME_OVER │
              │  │"Correct! │  │"Wrong!   │  ← Random failure prompt
              │  │ Let's go │  │ It was:  │
              │  │ to round │  │ apple,   │
              │  │ {n+1}!*  │  │ banana,  │  ← Random success prompt
              │  └────┬─────┘  │ cat.     │
              │       │        │ Score: X"│
              │       │        └────┬─────┘
              │       │             │
              │       │             ▼
              │       │        ┌──────────┐
              │       │        │  ENDED   │
              │       │        │(terminal)│
              │       │        └──────────┘
              │       │
              │       ▼
              │  Increase round count
              │  Add +1 word to sequence
              └── (loop back to SPEAK_SEQUENCE)
```

### Round Progression

| Round | Words in Sequence | Difficulty |
|-------|------------------|------------|
| 1     | 3                | Easy       |
| 2     | 4                | Easy       |
| 3     | 5                | Medium     |
| 4     | 6                | Medium     |
| 5     | 7                | Hard       |
| 6     | 8                | Hard       |
| 7     | 9                | Expert     |
| 8     | 10               | Expert     |
| 9     | 11               | Master     |
| 10    | 12               | Grandmaster|

**Max rounds:** 10 (configurable)
**Word pool:** 100+ common words (animals, fruits, objects, colors, etc.)

---

## 6. Database Schema

### Connection

```
Database:     the-memory-host
Port:         5432
User:         postgres
Password:     password
Host:         localhost (or service name in Docker)
```

### PostgreSQL

```sql
-- ============================================
-- Sessions table
-- ============================================
CREATE TABLE sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_name         VARCHAR(100) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'active',
        -- 'active' | 'completed' | 'interrupted'
    score               INTEGER NOT NULL DEFAULT 0,
    current_round       INTEGER NOT NULL DEFAULT 0,
    max_rounds          INTEGER NOT NULL DEFAULT 10,
    room_url            TEXT NOT NULL,
    room_name           VARCHAR(100) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at            TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_created ON sessions(created_at DESC);

-- ============================================
-- Rounds table
-- ============================================
CREATE TABLE rounds (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    round_number        INTEGER NOT NULL,
    word_sequence       JSONB NOT NULL,
        -- e.g. ["apple", "banana", "cat"]
    user_response       JSONB,
        -- e.g. ["apple", "banana", "cat"]; NULL if not yet answered
    is_correct          BOOLEAN,
        -- NULL = pending, TRUE = correct, FALSE = wrong
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    answered_at         TIMESTAMPTZ,

    -- Prevent double-scoring: one response per round
    CONSTRAINT uq_session_round UNIQUE (session_id, round_number)
);

CREATE INDEX idx_rounds_session ON rounds(session_id);

-- ============================================
-- Leaderboard (materialized query or view)
-- ============================================
CREATE VIEW leaderboard AS
SELECT
    s.player_name,
    MAX(s.score) AS best_score,
    MAX(s.current_round) AS best_round,
    COUNT(s.id) AS games_played,
    MAX(s.created_at) AS last_played
FROM sessions s
WHERE s.status = 'completed'
GROUP BY s.player_name
ORDER BY best_score DESC, best_round DESC;
```

### SQLAlchemy Models (Python)

```python
# models/session.py
class Session(Base):
    __tablename__ = "sessions"
    id: UUID          # primary key
    player_name: str
    status: str       # 'active' | 'completed' | 'interrupted'
    score: int
    current_round: int
    max_rounds: int
    room_url: str
    room_name: str
    created_at: datetime
    ended_at: Optional[datetime]
    updated_at: datetime

    rounds: list[Round] = relationship("Round", back_populates="session")

# models/round.py
class Round(Base):
    __tablename__ = "rounds"
    id: UUID
    session_id: UUID (FK → sessions.id)
    round_number: int
    word_sequence: list[str]   # JSONB
    user_response: Optional[list[str]]  # JSONB, nullable
    is_correct: Optional[bool]  # nullable
    created_at: datetime
    answered_at: Optional[datetime]
```

---

## 7. Caching Strategy

Use **in-memory caching** (Python `cachetools.TTLCache`) — no Redis dependency.

### Cache Configuration

```python
from cachetools import TTLCache

# Active session data: 30 min TTL, max 100 sessions
active_sessions: TTLCache = TTLCache(maxsize=100, ttl=1800)

# Leaderboard cache: 60 second TTL
leaderboard_cache: TTLCache = TTLCache(maxsize=10, ttl=60)

# Active round state: 30 min TTL, max 500 rounds
round_cache: TTLCache = TTLCache(maxsize=500, ttl=1800)
```

### Cache Key Pattern

| Cache Key                | Value                           | TTL        | Purpose                          |
|--------------------------|---------------------------------|------------|----------------------------------|
| `session:{id}`           | Session JSON (state, round, etc.) | 30 minutes | Quick active session lookup      |
| `session:{id}:round:{n}` | Round JSON (sequence, words)    | 30 minutes | Current round state              |
| `leaderboard`            | Top 20 scores + player names    | 60 seconds | Leaderboard display              |
| `word_pool:used:{hash}`  | "1" (existence flag)            | 24 hours   | Avoid repeating recent sequences |

### When to Cache / Miss Cache

- **Session start:** Write session to PostgreSQL + cache simultaneously
- **Game state poll:** Read from in-memory cache (fast), fallback to DB
- **Round validation:** Check cache for session state → validate → write round to DB → update cache
- **Leaderboard:** Serve from cached version, refresh every 60s via background task
- **Session end:** Write final state to DB, remove from cache

---

## 8. API Endpoints

### Backend (FastAPI)

| Method | Endpoint                         | Description                                 | Auth     |
|--------|----------------------------------|---------------------------------------------|----------|
| POST   | `/api/sessions`                  | Create new session + SmallWebRTC room       | Public   |
| GET    | `/api/sessions/{session_id}`      | Get game state (score, round, status)       | Public   |
| POST   | `/api/sessions/{session_id}/end`  | End a session manually                      | Public   |
| GET    | `/api/leaderboard`               | Get top scores                              | Public   |
| GET    | `/api/health`                    | Health check                                | Public   |

### Next.js API Routes (BFF Layer)

| Method | Route                                    | Description                                   |
|--------|------------------------------------------|-----------------------------------------------|
| POST   | `/api/sessions`                          | Proxies to FastAPI; creates session + returns room URL |
| GET    | `/api/sessions/[id]`                     | Proxies game state from FastAPI               |
| POST   | `/api/sessions/[id]/end`                 | Proxies end session                           |
| GET    | `/api/leaderboard`                       | Proxies leaderboard                           |

### Response Schemas

**POST /api/sessions → 201**
```json
{
  "session_id": "uuid",
  "player_name": "Alice",
  "room_url": "http://localhost:3001/room/abc123",
  "room_token": "eyJhbG...",
  "status": "active",
  "created_at": "2026-07-24T10:00:00Z"
}
```

**GET /api/sessions/{id} → 200**
```json
{
  "session_id": "uuid",
  "player_name": "Alice",
  "status": "active",
  "score": 3,
  "current_round": 1,
  "total_rounds": 5,
  "created_at": "2026-07-24T10:00:00Z"
}
```

**GET /api/leaderboard → 200**
```json
{
  "leaderboard": [
    {
      "player_name": "Alice",
      "best_score": 15,
      "best_round": 5,
      "games_played": 3,
      "last_played": "2026-07-24T10:00:00Z"
    }
  ]
}
```

---

## 9. Pipecat Pipeline Design

### Pipeline Assembly (`bot.py`)

```python
import asyncio
import random
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.deepgram import DeepgramSTTService, DeepgramTTSService
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3

# Custom game processor
from game_processor import MemoryGameProcessor
from prompt_templates import PromptTemplateSelector

# --- SmallWebRTC Transport ---
# (Using a lightweight WebSocket/Signaling based transport)
transport = SmallWebRTCTransport(
    room_url=room_url,
    token=bot_token,
    bot_name="Memory Game Host",
    params=TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
        vad_audio_passthrough=True,
    ),
)

# --- Turn detection ---
transport.use_smart_turn(
    turn_analyzer=LocalSmartTurnAnalyzerV3(),
    stop_secs=0.5,
)

# --- Services ---
stt = DeepgramSTTService(
    api_key=os.getenv("DEEPGRAM_API_KEY"),
    model="nova-2",
)

tts = DeepgramTTSService(
    api_key=os.getenv("DEEPGRAM_API_KEY"),
    voice="aura-asteria-en",  # friendly, energetic female voice
)

# --- Prompt Template Selector (replaces LLM) ---
prompt_selector = PromptTemplateSelector()

# --- Game State ---
game_state = GameState()

# --- Custom Game Processor ---
game_processor = MemoryGameProcessor(
    game_state=game_state,
    db_session=db_session,
    cache=cache,
    prompt_selector=prompt_selector,
)

# --- Assemble Pipeline ---
pipeline = Pipeline([
    transport.input(),           # Audio from user via WebRTC
    stt,                         # Speech → Text
    game_processor,              # Core game logic + prompt template selection
    tts,                         # Text → Speech
    transport.output(),          # Audio to user via WebRTC
])

# --- Run ---
runner = PipelineRunner()
task = PipelineTask(pipeline)
await runner.run(task)
```

### Key Design Decisions

1. **MemoryGameProcessor is the central orchestrator** — it intercepts user transcript frames, validates game responses, selects random prompt templates for bot speech, and controls the game flow.

2. **No LLM service** — All bot dialog comes from pre-written prompt templates. The processor selects a random template from the appropriate category (start, round_intro, success, failure, game_over).

3. **GameState is shared** — a plain Python dataclass that tracks `current_round`, `expected_sequence`, `current_state`, `score`, etc.

4. **Turn detection uses SmartTurn** — more natural than simple timeout, uses intonation/linguistic cues.

5. **Interruptions enabled** — Pipecat's native interruption support stops TTS when user starts speaking mid-bot-speech.

---

## 10. MemoryGameProcessor (Core Logic)

This is the **most important custom component** — a Pipecat `FrameProcessor` that acts as the game engine.

### Class Structure

```python
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    TranscriptFrame,
    StartFrame,
    EndFrame,
)
from enum import Enum
import random
from dataclasses import dataclass, field
from typing import Optional

class GameState(Enum):
    IDLE = "idle"
    START_GAME = "start_game"
    SPEAK_SEQUENCE = "speak_sequence"
    LISTEN = "listen"
    VALIDATE = "validate"
    ROUND_PASS = "round_pass"
    GAME_OVER = "game_over"
    ENDED = "ended"

@dataclass
class GameData:
    """Mutable game state shared across the processor."""
    state: GameState = GameState.IDLE
    current_round: int = 0
    score: int = 0
    expected_sequence: list[str] = field(default_factory=list)
    user_transcript_buffer: list[str] = field(default_factory=list)
    session_id: Optional[str] = None
    player_name: str = "Player"
    is_validating: bool = False  # Prevents re-entry during validation
    incorrect_round_data: Optional[dict] = None  # Store for game over message


class MemoryGameProcessor(FrameProcessor):
    def __init__(self, game_data: GameData, db_session, cache,
                 prompt_selector, word_pool: list[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.game = game_data
        self.db = db_session
        self.cache = cache
        self.prompt_selector = prompt_selector
        self.word_pool = word_pool or DEFAULT_WORD_POOL

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # === HANDLE FRAME TYPES ===

        # 1. User started speaking (interruption or response)
        if isinstance(frame, UserStartedSpeakingFrame):
            await self._on_user_started_speaking()

        # 2. User stopped speaking (turn complete)
        elif isinstance(frame, UserStoppedSpeakingFrame):
            await self._on_user_stopped_speaking()

        # 3. User transcript (transcribed speech from STT)
        elif isinstance(frame, TranscriptFrame):
            await self._on_transcript(frame)

        # 4. Session start
        elif isinstance(frame, StartFrame):
            await self._on_start()

        # 5. Session end
        elif isinstance(frame, EndFrame):
            await self._on_end()

        # Always forward the frame to maintain pipeline flow
        await self.push_frame(frame, direction)
```

### Core Methods

```python
async def _on_user_started_speaking(self):
    """Handle user interrupting or beginning to speak."""
    if self.game.state == GameState.SPEAK_SEQUENCE:
        # User interrupted bot mid-sequence-speech
        self.game.state = GameState.LISTEN
        await self.push_frame(EndFrame())
        logger.info(f"User interrupted bot during sequence speech")

    elif self.game.state == GameState.LISTEN:
        self.game.user_transcript_buffer = []


async def _on_user_stopped_speaking(self):
    """User finished their turn — transition to validation."""
    if self.game.state == GameState.LISTEN and not self.game.is_validating:
        self.game.state = GameState.VALIDATE
        await self._validate_response()


async def _on_transcript(self, frame: TranscriptFrame):
    """Collect transcribed words from user."""
    if self.game.state == GameState.LISTEN:
        self.game.user_transcript_buffer.append(frame.text)


async def _validate_response(self):
    """Core validation logic — pure Python, NOT LLM-dependent."""
    self.game.is_validating = True

    try:
        user_words = self._parse_transcript_to_words(
            self.game.user_transcript_buffer
        )
        expected = self.game.expected_sequence

        # === COMPARE ===
        is_correct = self._compare_sequences(expected, user_words)

        # === PREVENT DOUBLE SCORING (DB check) ===
        already_scored = await self._check_already_scored()
        if already_scored:
            logger.warning("Double-scoring attempt blocked")
            return

        # === RECORD ROUND ===
        round_record = await self._save_round_to_db(
            round_number=self.game.current_round,
            word_sequence=expected,
            user_response=user_words,
            is_correct=is_correct,
        )

        # === UPDATE CACHE ===
        await self._update_cache()

        if is_correct:
            # Correct! Select a random success prompt
            self.game.score += self.game.current_round
            self.game.current_round += 1

            if self.game.current_round > self.game.max_rounds:
                await self._on_game_won()
            else:
                self.game.state = GameState.ROUND_PASS
                self.game.expected_sequence = self._generate_sequence(
                    round_number=self.game.current_round
                )
                # Select and inject a random round-pass prompt
                prompt = self.prompt_selector.get("round_pass")
                await self._say(prompt.format(
                    score=self.game.score,
                    round_number=self.game.current_round,
                    sequence=", ".join(self.game.expected_sequence),
                ))
        else:
            # Wrong answer — select a random failure prompt
            self.game.incorrect_round_data = {
                "expected": expected,
                "user_said": user_words,
                "round": self.game.current_round,
                "score": self.game.score,
            }
            self.game.state = GameState.GAME_OVER
            prompt = self.prompt_selector.get("game_over")
            await self._say(prompt.format(
                correct_sequence=", ".join(expected),
                user_said=", ".join(user_words),
                score=self.game.score,
                round_number=self.game.current_round,
            ))

    finally:
        self.game.user_transcript_buffer = []
        self.game.is_validating = False


async def _say(self, text: str):
    """Push a TextFrame with the bot's speech to the pipeline."""
    await self.push_frame(TextFrame(text))


def _compare_sequences(self, expected: list[str], actual: list[str]) -> bool:
    """Pure Python comparison — exact match, case-insensitive, strip punctuation."""
    expected_norm = [w.strip().lower().rstrip(".,!?") for w in expected]
    actual_norm = [w.strip().lower().rstrip(".,!?") for w in actual]
    return expected_norm == actual_norm
```

### Sequence Generation

```python
WORD_POOL = [
    "apple", "banana", "cherry", "dragon", "eagle", "forest",
    "garden", "harbor", "island", "jaguar", "knight", "lemon",
    "mountain", "night", "orange", "piano", "queen", "river",
    "sunset", "tiger", "umbrella", "violin", "whisper", "yellow",
    "zebra", "castle", "diamond", "emerald", "feather", "guitar",
    "honey", "iceberg", "jewel", "koala", "lantern", "melody",
    "nebula", "ocean", "pepper", "rainbow", "silver", "thunder",
    "violet", "winter", "autumn", "butterfly", "chocolate",
    "dolphin", "elephant", "firefly", "ginger", "horizon",
    "jasmine", "kangaroo", "lavender", "marble", "nectar",
    "olive", "pancake", "quartz", "rocket", "sapphire",
]

def generate_sequence(round_number: int, used_sequences: set) -> list[str]:
    """Generate a unique word sequence for the given round."""
    word_count = round_number + 2
    while True:
        sequence = random.sample(WORD_POOL, word_count)
        seq_hash = tuple(sequence)
        if seq_hash not in used_sequences:
            used_sequences.add(seq_hash)
            return sequence
```

---

## 11. Prompt Templates & Random Selection

The LLM has been replaced with a **PromptTemplateSelector** that maintains categorized lists of pre-written dialog templates. On each game event, a random template is selected from the appropriate category, providing variety without requiring an external LLM.

### Template Categories

| Category      | Trigger Event                     | Description                               |
|---------------|-----------------------------------|-------------------------------------------|
| `start`       | Game begins (user joins)          | Welcome messages, game instructions       |
| `round_intro` | New round starts                  | Announce round number and word sequence   |
| `success`     | User answers correctly            | Congratulations, encouragement            |
| `failure`     | User answers incorrectly          | Gentle reveal of correct answer           |
| `game_over`   | Wrong answer or game won          | Final score announcement                  |
| `interrupt`   | User interrupts bot               | Recovery phrases after interruption       |
| `waiting`     | Bot waiting for user to respond   | Gentle prompts to encourage response      |

### Template Selector Implementation

```python
import random
from typing import Optional


class PromptTemplateSelector:
    """Selects random prompt templates for bot dialog."""

    def __init__(self):
        self.templates = {
            "start": [
                "Welcome to the Memory Host, {player_name}! I'm going to say a "
                "sequence of words. Your job is to repeat them back to me exactly "
                "as I said them. Ready? Let's begin!",
                "Hey there, {player_name}! Welcome to the memory challenge! "
                "Listen carefully to each word I say, and then repeat them back "
                "to me in the same order. Let's see how far you can go!",
                "Hello, {player_name}, and welcome to The Memory Host! "
                "I'll speak a sequence of words — your task is to remember them "
                "and repeat them back. The sequences get longer each round. "
                "Good luck!",
            ],
            "round_intro": [
                "Round {round_number}. Here are your words: {sequence}. "
                "Now it's your turn to repeat them back to me.",
                "Okay, round {round_number}! Listen closely: {sequence}. "
                "Go ahead and repeat that back.",
                "Here comes round {round_number}: {sequence}. "
                "Take your time and say them back when you're ready.",
            ],
            "success": [
                "That's correct! You've got a great memory. Let's move to round {round_number}. "
                "Your score is now {score}. Here's your next sequence: {sequence}.",
                "Perfect! You nailed it. On to round {round_number}! "
                "Score: {score}. Listen up: {sequence}.",
                "Absolutely right! You're on fire. Round {round_number} coming up. "
                "Score: {score}. Your words are: {sequence}.",
                "Correct! Excellent memory. Let's see how you do in round {round_number}. "
                "Current score: {score}. Here's your new sequence: {sequence}.",
            ],
            "failure": [
                "Oh, that's not quite right. The correct sequence was: {correct_sequence}. "
                "You said: {user_said}. Your final score is {score}. "
                "Thanks for playing The Memory Host!",
                "Almost! The right answer was: {correct_sequence}. "
                "You said: {user_said}. Game over! Final score: {score}. "
                "Great effort!",
                "Sorry, that wasn't correct. I was looking for: {correct_sequence}. "
                "You replied with: {user_said}. "
                "Game over! You scored {score} points. Well played!",
            ],
            "game_over": [
                "That's the game! You've completed all rounds. "
                "Your final score is {score}. You're a memory master! "
                "Congratulations, {player_name}!",
                "Incredible! You made it through all the rounds! "
                "Final score: {score}. That's amazing! Thanks for playing!",
                "You did it! Every round completed with a perfect score of {score}! "
                "You are the ultimate Memory Host champion, {player_name}!",
            ],
            "interrupt": [
                "Oh, you cut me off! Go ahead, I'm listening.",
                "Sorry, go ahead! What were you going to say?",
                "You jumped in! That's fine, take the floor.",
            ],
            "waiting": [
                "Take your time, I'm listening...",
                "No rush, just repeat the words when you're ready.",
                "I'm still here, waiting for your response.",
            ],
        }

    def get(self, category: str, default: Optional[str] = None) -> str:
        """Get a random template from the specified category."""
        templates = self.templates.get(category)
        if not templates:
            return default or ""
        return random.choice(templates)

    def add_template(self, category: str, template: str):
        """Add a new template to a category."""
        if category not in self.templates:
            self.templates[category] = []
        self.templates[category].append(template)
```

### How Templates Are Selected

1. When a game event occurs (round pass, game over, etc.), the `MemoryGameProcessor` calls `prompt_selector.get("category")`
2. The selector returns a **random template** from that category
3. Template variables like `{player_name}`, `{score}`, `{sequence}`, `{correct_sequence}` are filled in by the processor
4. The formatted text is pushed as a `TextFrame` into the pipeline → TTS → audio out

This approach provides natural variety in the bot's responses without the cost, latency, or complexity of an LLM. New templates can be added easily by appending to the appropriate list.

---

## 12. Frontend Architecture (Next.js)

### Pages & Routes

```
/                           → Landing page (start game)
/game/[sessionId]           → Game room (SmallWebRTC + game state)
/leaderboard                → Leaderboard page
```

### Component Tree

```
<App>
  ├── <Layout> (global styles, nav)
  │   ├── <HomePage>
  │   │   ├── PlayerNameInput
  │   │   ├── StartGameButton → POST /api/sessions → redirect to /game/[id]
  │   │   └── RecentScores (mini leaderboard)
  │   │
  │   ├── <GamePage>
  │   │   ├── <GameHeader>
  │   │   │   ├── PlayerName
  │   │   │   ├── Score
  │   │   │   ├── RoundNumber
  │   │   │   └── GameStatus ('active' | 'completed')
  │   │   │
  │   │   ├── <WebRTCRoom> (client-side only, dynamic import)
  │   │   │   └── SmallWebRTC video/audio element
  │   │   │
  │   │   ├── <GameLog>
  │   │   │   └── RoundHistory (shows expected vs actual for past rounds)
  │   │   │
  │   │   └── <GameOverModal> (shown on game end)
  │   │       ├── FinalScore
  │   │       ├── RoundsPassed
  │   │       └── PlayAgainButton
  │   │
  │   └── <Leaderboard>
  │       └── ScoreTable (player name, best score, games played)
```

### Key Implementation Details

#### 1. Dynamic Import for SmallWebRTC (SSR-Safe)

```typescript
// components/WebRTCRoom.tsx (client-only component)
"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";

export function WebRTCRoom({ roomUrl, token }: { roomUrl: string; token: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);

  useEffect(() => {
    if (!roomUrl || !videoRef.current) return;

    const initWebRTC = async () => {
      // SmallWebRTC uses standard WebRTC APIs
      // Connect to signaling server, create peer connection,
      // set up audio/video tracks, etc.
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
      });

      pc.ontrack = (event) => {
        if (videoRef.current && event.track.kind === "audio") {
          // Attach audio track
          const audioStream = new MediaStream([event.track]);
          videoRef.current.srcObject = audioStream;
        }
      };

      // Connect to signaling server at roomUrl with token
      await connectToSignalingServer(pc, roomUrl, token);
      peerConnectionRef.current = pc;
    };

    initWebRTC();

    return () => {
      peerConnectionRef.current?.close();
    };
  }, [roomUrl, token]);

  return <audio ref={videoRef} autoPlay />;
}
```

#### 2. Game State Polling

```typescript
// hooks/useGameState.ts
export function useGameState(sessionId: string | null) {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!sessionId) return;

    const poll = async () => {
      try {
        const res = await fetch(`/api/sessions/${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          setGameState(data);
          setIsLoading(false);

          if (data.status === "completed") {
            return; // Stop polling
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    poll();
    const interval = setInterval(poll, 2000);

    return () => clearInterval(interval);
  }, [sessionId]);

  return { gameState, isLoading };
}
```

#### 3. Game Page

```typescript
// app/game/[sessionId]/page.tsx
export default function GamePage({ params }: { params: { sessionId: string } }) {
  const { gameState, isLoading } = useGameState(params.sessionId);

  if (isLoading) return <LoadingSkeleton />;
  if (!gameState) return <ErrorState />;

  return (
    <div className="game-container">
      <GameHeader
        playerName={gameState.player_name}
        score={gameState.score}
        round={gameState.current_round}
        status={gameState.status}
      />

      <WebRTCRoom
        roomUrl={gameState.room_url}
        token={gameState.room_token}
      />

      <GameLog sessionId={params.sessionId} />

      {gameState.status === "completed" && (
        <GameOverModal
          score={gameState.score}
          round={gameState.current_round}
          sessionId={params.sessionId}
        />
      )}
    </div>
  );
}
```

#### 4. API Route (BFF)

```typescript
// app/api/sessions/route.ts
import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function POST(request: Request) {
  const body = await request.json();

  const response = await fetch(`${BACKEND_URL}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
```

---

## 13. Interruption Handling

Interruptions occur when the **user starts speaking while the bot is talking**. Pipecat handles this natively, but the `MemoryGameProcessor` needs to respond appropriately.

### Flow

```
Bot is speaking sequence: "Round 1: apple, banana, cat..."
                                      │
                 User interrupts: "Wait, I forgot—"
                                      │
                                      ▼
              ┌──────────────────────────────────────┐
              │  UserStartedSpeakingFrame fires       │
              │                                       │
              │  1. Pipecat stops TTS output          │
              │  2. MemoryGameProcessor transitions:  │
              │     SPEAK_SEQUENCE → LISTEN           │
              └──────────────────────────────────────┘
                                      │
                 User finishes speaking
                                      │
                                      ▼
              ┌──────────────────────────────────────┐
              │  UserStoppedSpeakingFrame fires       │
              │                                       │
              │  1. SmartTurn detects turn end        │
              │  2. MemoryGameProcessor → VALIDATE    │
              │  3. Compare response to expected      │
              └──────────────────────────────────────┘
```

### Code Implementation

```python
async def _on_user_started_speaking(self):
    if self.game.state in (GameState.SPEAK_SEQUENCE, GameState.ROUND_PASS):
        # User interrupted bot — stop bot's output
        self.game.state = GameState.LISTEN
        self.game.user_transcript_buffer = []

        # Push an EndFrame to stop TTS
        await self.push_frame(EndFrame())

        # Optionally play a short interruption acknowledgment template
        interrupt_prompt = self.prompt_selector.get("interrupt")
        if interrupt_prompt:
            await self.push_frame(TextFrame(interrupt_prompt))

        logger.info("User interrupted during bot speech — transitioning to LISTEN")
```

### Recovery Behavior

The bot recovers gracefully because the game state is intact:
- `expected_sequence` is already set
- The processor simply transitions to LISTEN and waits for input
- When user finishes speaking, normal validation happens

---

## 14. Double-Scoring Prevention

Double-scoring is prevented at **three layers**:

### Layer 1: State Machine Guard (In-Memory)

```python
# In MemoryGameProcessor
self.game.is_validating = False  # Flag preventing re-entry

async def _validate_response(self):
    if self.game.is_validating:
        logger.warning("Validation already in progress — skipping")
        return
    self.game.is_validating = True
    # ... validation logic ...
    self.game.is_validating = False
```

### Layer 2: Database Constraint

```sql
-- UNIQUE constraint on (session_id, round_number)
-- Prevents a second round record for the same round
CONSTRAINT uq_session_round UNIQUE (session_id, round_number)
```

### Layer 3: Application-Level Check

```python
async def _check_already_scored(self) -> bool:
    """Check if this round already has a response recorded."""
    existing = await self.db.execute(
        select(Round).where(
            Round.session_id == self.game.session_id,
            Round.round_number == self.game.current_round,
            Round.user_response.isnot(None)
        )
    )
    return existing is not None
```

---

## 15. Project Structure

```
the-memory-host/
├── README.md
├── ARCHITECTURE.md                    # This document
├── .env.example
├── .gitignore
│
├── backend/                           # Python backend (FastAPI + Pipecat)
│   ├── pyproject.toml
│   ├── requirements.txt
│   │
│   ├── bot.py                         # Pipecat pipeline entrypoint
│   ├── game_processor.py              # MemoryGameProcessor (custom FrameProcessor)
│   ├── game_state.py                  # Game state enum + dataclass
│   ├── game_logic.py                  # Sequence generation, validation (pure Python)
│   ├── word_pool.py                   # Hardcoded word list
│   ├── prompt_templates.py            # Prompt template selector & template lists
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app
│   │   ├── routes.py                  # API endpoints
│   │   ├── models.py                  # Pydantic request/response models
│   │   └── deps.py                    # Dependency injection (DB, cache)
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                    # SQLAlchemy Base
│   │   ├── session.py                 # Session model
│   │   └── round.py                   # Round model
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py                # Database connection setup
│   │   └── migrations/                # Alembic migrations
│   │
│   ├── cache.py                       # In-memory cache layer (TTLCache)
│   ├── config.py                      # Environment config
│   │
│   └── tests/
│       ├── test_game_logic.py         # Unit tests for validation/sequence gen
│       ├── test_api.py                # API endpoint tests
│       ├── test_prompt_templates.py   # Prompt template selection tests
│       └── test_processor.py          # Mock pipeline tests
│
├── frontend/                          # Next.js frontend
│   ├── next.config.js
│   ├── package.json
│   ├── tsconfig.json
│   │
│   ├── app/
│   │   ├── layout.tsx                 # Root layout
│   │   ├── page.tsx                   # Landing page (start game)
│   │   ├── loading.tsx                # Loading state
│   │   ├── globals.css                # Global styles
│   │   │
│   │   ├── game/
│   │   │   └── [sessionId]/
│   │   │       └── page.tsx           # Game room page
│   │   │
│   │   └── leaderboard/
│   │       └── page.tsx               # Leaderboard page
│   │
│   ├── components/
│   │   ├── GameHeader.tsx             # Score, round, status display
│   │   ├── WebRTCRoom.tsx             # SmallWebRTC audio/video wrapper
│   │   ├── PlayerNameForm.tsx         # Player name input
│   │   ├── GameLog.tsx                # Round history
│   │   ├── GameOverModal.tsx          # End-game modal
│   │   ├── LeaderboardTable.tsx       # Leaderboard display
│   │   └── LoadingSkeleton.tsx        # Loading states
│   │
│   ├── hooks/
│   │   ├── useGameState.ts            # Poll game state
│   │   └── useLeaderboard.ts          # Fetch leaderboard
│   │
│   ├── lib/
│   │   └── api.ts                     # API client helper
│   │
│   └── public/
│       └── favicon.ico
│
└── docker-compose.yml                 # PostgreSQL + backend
```

---

## 16. Implementation Roadmap

### Phase 1 — Foundation (Steps 1-4)

| Step | Task | Files | Est. Time |
|------|------|-------|-----------|
| 1 | **Project scaffold** — Python venv, FastAPI, config, Docker | `backend/pyproject.toml`, `backend/config.py`, `docker-compose.yml` | 1 hr |
| 2 | **Word pool + game logic** — 100+ words, sequence generation, validation | `backend/word_pool.py`, `backend/game_logic.py` | 1 hr |
| 3 | **Game state machine** — enum, dataclass, transitions | `backend/game_state.py` | 30 min |
| 4 | **Database models + migrations** — SQLAlchemy + Alembic | `backend/models/*`, `backend/db/*` | 1.5 hr |

### Phase 2 — Backend APIs (Steps 5-6)

| Step | Task | Files | Est. Time |
|------|------|-------|-----------|
| 5 | **FastAPI routes** — session CRUD, leaderboard, SmallWebRTC room creation | `backend/api/*` | 2 hr |
| 6 | **Cache layer** — in-memory TTLCache | `backend/cache.py` | 30 min |

### Phase 3 — Voice Pipeline (Steps 7-10)

| Step | Task | Files | Est. Time |
|------|------|-------|-----------|
| 7 | **Prompt templates** — write categorized templates with random selection | `backend/prompt_templates.py` | 1 hr |
| 8 | **MemoryGameProcessor** — custom FrameProcessor with prompt template integration | `backend/game_processor.py` | 3 hr |
| 9 | **Pipecat pipeline assembly** — SmallWebRTC transport + STT + TTS + processor | `backend/bot.py` | 2 hr |
| 10 | **Interruption handling** — wire up UserStartedSpeakingFrame → graceful recovery | `backend/game_processor.py` | 1 hr |

### Phase 4 — Frontend (Steps 11-14)

| Step | Task | Files | Est. Time |
|------|------|-------|-----------|
| 11 | **Next.js scaffold** — pages, layout, API routes (BFF), styling | `frontend/*` | 1 hr |
| 12 | **SmallWebRTC integration** — WebRTC client, room join, SSR-safe dynamic import | `frontend/components/WebRTCRoom.tsx` | 1.5 hr |
| 13 | **Game state display** — polling hook, header, game log, game over modal | `frontend/hooks/useGameState.ts`, components | 1.5 hr |
| 14 | **Leaderboard page** — fetch from API, display table | `frontend/app/leaderboard/page.tsx` | 30 min |

### Phase 5 — Polish & Testing (Steps 15-17)

| Step | Task | Files | Est. Time |
|------|------|-------|-----------|
| 15 | **Double-scoring prevention** — DB constraints + application checks | `backend/game_processor.py`, DB migration | 30 min |
| 16 | **Unit tests** — game logic, API, processor, prompt templates | `backend/tests/*` | 2 hr |
| 17 | **README + setup instructions** — environment, running instructions | `README.md` | 1 hr |

**Total estimated time: ~18 hours**

---

## 17. Setup & Environment Variables

### `.env.example`

```bash
# === Deepgram (STT + TTS) ===
# Generate at: https://console.deepgram.com/
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# === Database (PostgreSQL) ===
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/the-memory-host

# === SmallWebRTC Signaling Server ===
SMALLWEBRTC_SERVER_URL=http://localhost:3001
SMALLWEBRTC_API_KEY=your_smallwebrtc_key

# === Bot ===
BOT_NAME=Memory Game Host
MAX_ROUNDS=10
LOG_LEVEL=INFO

# === Frontend ===
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### Getting a Deepgram API Key

1. Go to [deepgram.com](https://deepgram.com)
2. Sign up for a free account
3. Navigate to the API Keys section in the console
4. Create a new API key
5. Copy the key to `DEEPGRAM_API_KEY` in your `.env` file

### Running Locally

```bash
# 1. Start PostgreSQL
docker-compose up -d postgres

# 2. Start SmallWebRTC signaling server
# (follow smallwebrtc setup instructions)
npx smallwebrtc --port 3001

# 3. Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn api.main:app --reload --port 8000

# 4. Frontend
cd frontend
npm install
npm run dev

# 5. Start Pipecat bot (separate terminal)
cd backend
python bot.py
```

### Production Migration (Daily.co)

When moving to production, swap the transport layer:

1. Replace `SmallWebRTCTransport` with `DailyTransport` in `bot.py`
2. Update room creation endpoints to use Daily.co REST API
3. Update frontend `WebRTCRoom.tsx` to use `@daily-co/daily-js`
4. Add `DAILY_API_KEY` and `DAILY_DOMAIN` to environment variables
5. No other changes needed — the rest of the architecture remains identical

---

## Appendix: Key Pipecat Concepts

| Concept | Description |
|---------|-------------|
| **Frame** | Unit of data in pipeline — audio, text, control signals |
| **FrameProcessor** | Building block that receives, processes, and pushes frames |
| **Pipeline** | Ordered chain of processors that frames flow through |
| **Transport** | I/O interface (SmallWebRTC, Daily, WebSocket, etc.) |
| **VAD** | Voice Activity Detection — SileroVADAnalyzer |
| **SmartTurn** | ML-based turn-end detection using intonation |
| **STT Service** | Speech-to-text (DeepgramSTTService) |
| **TTS Service** | Text-to-speech (DeepgramTTSService) |
| **FrameDirection** | DOWNSTREAM (user→bot) or UPSTREAM (bot→user) |
