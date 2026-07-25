# The Memory Host — Architecture & Implementation Plan

> **Framework:** Pipecat (Python)
> **Frontend:** Next.js (TypeScript)
> **Transport:** SmallWebRTC
> **STT/TTS:** Deepgram (Nova-2 / Aura 2)
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
15. [Retry & Scoring System](#15-retry--scoring-system)
16. [Push-to-Talk Recording](#16-push-to-talk-recording)
17. [Implementation Roadmap](#17-implementation-roadmap)
18. [Logging](#18-logging)

---

## 1. System Overview

We are building a **voice-based Memory Card game** using the [Pipecat](https://github.com/pipecat-ai/pipecat) framework. The bot acts as a game show host:

1. **Bot speaks** each word individually with 1-second pauses
2. **User taps Start Recording** and speaks the words back
3. **User taps Stop Recording** — signal sent to bot for validation
4. **Bot evaluates** correctness (pure Python word-by-word comparison)
5. **Game progresses** — correct answers add more words each round
6. **Game ends** on wrong answer (after 3 retries) or max rounds reached
7. **Leaderboard** shows top 3 highest-scoring individual sessions

### Key Differences from v1

- **Two-service architecture** — REST API (port 8000) and Game Engine (port 3002) run as separate processes
- **No LLM** — all dialog via pre-written templates with random selection
- **Push-to-talk** — user explicitly starts/stops recording instead of VAD-based turn detection
- **Word-by-word partial scoring** — each correctly remembered word awards 1 point
- **Retry system** — 3 retries per round, best attempt saved
- **Pipeline stops on game over** — EndFrame pushed after final TTS completes
- **Top 3 individual sessions** — leaderboard shows highest-scoring sessions (not grouped by player)

---

## 2. Architecture Diagram

### Two-Service Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     FRONTEND SERVICE (Next.js 15)                │
│  Port 3000                                                      │
│                                                                  │
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
    │   │                  │      │                  │  │
    │   │  FastAPI         │◄────►│  FastAPI         │  │
    │   │                  │      │                  │  │
    │   │  • Sessions      │      │  • Signaling     │  │
    │   │  • Leaderboard   │      │    Server (3001) │  │
    │   │  • Health        │      │  • Voice Bot     │  │
    │   └────────┬────────┘      │  • Game Engine   │  │
    │            │               └──────────────────┘  │
    │            │                        │            │
    │   ┌────────▼────────┐               │            │
    │   │  PostgreSQL     │     WebRTC P2P             │
    │   │  (the-memory-   │     Audio Channel           │
    │   │   host)         │               │            │
    │   └─────────────────┘               ▼            │
    │                         ┌─────────────────────┐  │
    │                         │   PIPECAT BOT       │  │
    │                         │                     │  │
    │                         │ WebRTC Input        │  │
    │                         │     → Deepgram STT  │  │
    │                         │     → GameProcessor │  │
    │                         │     → Deepgram TTS  │  │
    │                         │     → WebRTC Output │  │
    │                         └─────────────────────┘  │
    └──────────────────────────────────────────────────┘
```

### High-Level Data Flow

```
┌──────────┐     POST /api/sessions     ┌────────────┐     POST /start-session  ┌──────────────┐
│  Next.js  │ ───────────────────────►  │ REST API   │ ─────────────────────►   │ Game Engine  │
│  Frontend │ ◄───────────────────────  │ (port 8000)│                          │ (port 3002)  │
│           │   201 + room_url, token   └────────────┘                          └──────────────┘
│           │
│           │     WebSocket Signaling (port 3001)
│    ┌──────┴──────┐    (same room)          ┌──────────────┐
│    │ SmallWebRTC │ ◄────────────────────►  │ Pipecat Bot  │
│    │ Client      │                         │ (bot.py)     │
│    └─────────────┘                         └──────────────┘
│           │
│           │     GET /api/sessions/:id  (polling for game state, 2s)
│           │ ◄─────────────────────────────────────────►
│           │     GET /api/leaderboard
└──────────┘
```

### Sequence Diagram

See [`docs/sequence-diagram.svg`](docs/sequence-diagram.svg) for a visual sequence diagram showing the complete game flow.

---

## 3. Tech Stack & Justification

| Component         | Service              | Free Tier / Cost                  | Why Choose                          |
|-------------------|----------------------|-----------------------------------|-------------------------------------|
| **Voice Pipeline**| Pipecat              | Open-source (MIT)                 | Industry standard for voice AI bots |
| **Transport**     | SmallWebRTC          | Free / Open-source                | Lightweight WebRTC signaling        |
| **STT**           | Deepgram Nova-2      | $200 free credits (≈43K mins)     | Low latency, high accuracy          |
| **TTS**           | Deepgram Aura 2      | $200 free credits                 | Natural voices, speed control       |
| **LLM**           | — (removed)          | —                                 | Using pre-written prompt templates  |
| **Database**      | PostgreSQL           | Free (self-hosted)                | Reliable, JSONB support             |
| **Cache**         | In-memory (TTLCache) | Free                              | Simple, no infra overhead           |
| **REST API**      | FastAPI (Python)     | Free                              | Async, fast, great DX               |
| **Frontend**      | Next.js (TypeScript) | Free                              | SSR, API routes, modern React       |

**Deepgram API Key:** Required for both STT (Nova-2) and TTS (Aura 2). Generate one at [deepgram.com](https://deepgram.com).

---

## 4. Services Breakdown

### Service 1: REST API (Python — FastAPI, Port 8000)

- **Session CRUD** — Create, read, update game sessions
- **Leaderboard** — Top 3 highest-scoring individual sessions
- **Round History** — Return saved rounds for a session
- **Health** — `/api/health` endpoint

### Service 2: Game Engine (Python — FastAPI + Pipecat, Port 3002)

- **Signaling Server** — WebSocket server (Port 3001) for WebRTC peer negotiation
- **Voice Bot** — Pipecat pipeline assembly (STT, TTS, GameProcessor)
- **Game Engine** — MemoryGameProcessor, word sequence generation, response validation
- **HTTP API** — `/start-session` receives requests from REST API

### Service 3: Frontend (Next.js — TypeScript, Port 3000)

- **Pages** — Landing, Game Room, Leaderboard
- **BFF API Routes** — Proxy requests to REST API
- **SmallWebRTC Client** — Join WebRTC room, audio/video
- **Game State Polling** — Poll REST API every 2s for game state
- **UI Components** — GameHeader, GameOverModal, LeaderboardTable, etc.

---

## 5. Game Flow & State Machine

### State Transitions

```
                         ┌──────────┐
                         │   IDLE   │
                         └────┬─────┘
                              │ StartFrame arrives
                              ▼
                    ┌───────────────────┐
                    │  START_GAME       │
                    │  Reset game data  │
                    │  Generate round 1 │
                    │  sequence         │
                    └────────┬──────────┘
                             │
                             ▼
                    ┌─────────────────────┐
                    │  SPEAK_SEQUENCE     │ ← Random welcome template
                    │  Bot says welcome  │   + individual word
                    │  then each word    │   announcements with 1s
                    │  individually      │   pauses
                    └─────────┬──────────┘
                              │ Bot finishes speaking
                              ▼
                    ┌─────────────────────┐
                    │     LISTEN          │ ← User taps Start
                    │  User_done event    │   Recording, speaks,
                    │  signals validation │   taps Stop Recording
                    └─────────┬──────────┘
                              │ user_done signal or transcript threshold
                              ▼
                    ┌─────────────────────┐
                    │    VALIDATE         │ ← Word-by-word
                    │  compare_word_by    │   comparison, partial
                    │  _word()            │   scoring
                    └─────────┬──────────┘
                              │
                    ┌─────────┴──────────┐
                    │                    │
               PERFECT              PARTIAL
                    │                    │
                    ▼                    ▼
          ┌────────────────┐   ┌────────────────────┐
          │  ROUND_PASS    │   │  RETRY             │
          │  +score, next  │   │  retries_remaining │
          │  round words   │   │  > 0 → re-announce │
          └───────┬────────┘   │  words             │
                  │            └─────────┬──────────┘
                  │                      │
                  │            ┌─────────▼──────────┐
                  │            │  retries exhausted │
                  │            └─────────┬──────────┘
                  │                      │
                  └─────────────────┬────┘
                                    │
                                    ▼
                          ┌──────────────────────┐
                          │  GAME_OVER           │
                          │  Bot says final msg  │
                          │  Push EndFrame       │
                          │  → pipeline stops    │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │  ENDED (terminal)    │
                          │  DB: status=completed│
                          │  Frontend: game over │
                          │    modal with button │
                          └──────────────────────┘
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
**Scoring:** Word-by-word match — each correctly remembered word = 1 point

When a user gets a partial score:
1. Bot says "Good try! You got X out of Y correct."
2. Bot re-announces each word individually with 1-second pauses
3. Bot says "Go ahead and repeat that back."
4. 5-second pause, then transitions to LISTEN
5. After 3 retries exhausted → Game Over, best retry score saved

When a user gets a perfect score:
1. Bot says "Correct! Moving to round X. Score: Y."
2. Bot announces new words individually
3. 5-second pause, transitions to LISTEN

---

## 6. Database Schema

### PostgreSQL Tables

#### `sessions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `player_name` | VARCHAR(100) | Player display name |
| `status` | VARCHAR(20) | `active` / `completed` / `interrupted` |
| `score` | INTEGER | Current/total score |
| `current_round` | INTEGER | Current round (0 = waiting) |
| `max_rounds` | INTEGER | Max rounds (default 10) |
| `room_url` | TEXT | SmallWebRTC room URL |
| `room_name` | VARCHAR(100) | Room identifier |
| `created_at` | TIMESTAMPTZ | Session creation |
| `ended_at` | TIMESTAMPTZ | Session end |
| `updated_at` | TIMESTAMPTZ | Last update |

#### `rounds`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `session_id` | UUID (FK → sessions) | Parent session |
| `round_number` | INTEGER | 1-indexed round |
| `word_sequence` | JSONB | Expected words array |
| `user_response` | JSONB (nullable) | User's spoken words |
| `is_correct` | BOOLEAN (nullable) | True/False |
| `created_at` | TIMESTAMPTZ | Creation |
| `updated_at` | TIMESTAMPTZ | Last update |
| `answered_at` | TIMESTAMPTZ | When answered |

**Constraint:** Unique on (`session_id`, `round_number`) — prevents double-scoring

### Leaderboard Query

The leaderboard shows the **top 3 individual sessions** (not grouped by player):

```sql
SELECT id, player_name, score, current_round, created_at
FROM sessions
WHERE status IN ('completed', 'interrupted')
  AND score > 0
ORDER BY score DESC, current_round DESC, created_at ASC
LIMIT 3;
```

---

## 7. Caching Strategy

In-memory caching (`cachetools.TTLCache`) — no Redis dependency.

| Cache | Key | TTL | Purpose |
|-------|-----|-----|---------|
| Active sessions | `session:{id}` | 30 min | Quick session lookup |
| Challenge state | `session:{id}:round:{n}` | 30 min | Current round state |
| Leaderboard | `leaderboard` | 60 sec | Cached top scores |
| Room → Session | `room:{name}` | 30 min | Room name lookup |

---

## 8. API Endpoints

### REST API (Port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sessions` | Create new session → notify game engine |
| `GET` | `/api/sessions/{id}` | Get game state (score, round, status) |
| `POST` | `/api/sessions/{id}/end` | End a session manually |
| `GET` | `/api/sessions/{id}/rounds` | Get round history |
| `GET` | `/api/leaderboard` | Top 3 individual sessions |
| `GET` | `/api/health` | Health check |

### Game Engine (Port 3002)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/start-session` | Start voice bot for a session |
| `GET` | `/health` | Health check |

### Signaling (Port 3001 — WebSocket)

| Type | Description |
|------|-------------|
| `join` | Register as peer (bot/receiver) |
| `offer` | SDP offer from client |
| `answer` | SDP answer from bot |
| `ice-candidate` | ICE candidate relay |
| `user_done` | Push-to-talk released |

---

## 9. Pipecat Pipeline Design

### Pipeline Assembly (`bot.py`)

```python
pipeline = Pipeline([
    transport.input(),              # Audio from user via WebRTC
    DeepgramSTTService(),           # Speech → Text (Nova-2)
    MemoryGameProcessor(...),        # Core game engine
    SlowerDeepgramTTSService(),     # Text → Speech (Aura 2, speed=0.9)
    transport.output(),             # Audio to user via WebRTC
])
```

### Key Design Decisions

1. **Two separate Python services** — REST API (FastAPI, port 8000) and Game Engine (FastAPI + Pipecat, port 3002)
2. **WebSocket signaling server** — runs inside the Game Engine process via FastAPI lifespan, port 3001
3. **`TTSSpeakFrame` over `TextFrame`** — ensures proper audio context lifecycle (prevents silent word drops)
4. **Push-to-talk** — user explicitly starts/stops recording, validation triggers on `user_done` signal
5. **No LLM** — all bot dialog from pre-written prompt templates with random selection
6. **Pipeline stops on game over** — `EndFrame` pushed after final TTS message
7. **British English voice** — `aura-2-pandora-en` with speed=0.9

---

## 10. MemoryGameProcessor (Core Logic)

The central orchestrator — a Pipecat `FrameProcessor` that acts as the game engine.

### Class: `MemoryGameProcessor(FrameProcessor)`

```
INPUT:  StartFrame, TranscriptionFrame, UserStartedSpeakingFrame,
        UserStoppedSpeakingFrame, EndFrame
OUTPUT: TTSSpeakFrame (bot speech)
```

### Core Methods

| Method | Trigger | Action |
|--------|---------|--------|
| `_on_start()` | `StartFrame` | Reset game, generate sequence, announce round |
| `_announce_round()` | Internal | Say intro + each word individually with 1s pauses |
| `_on_user_started_speaking()` | VAD | Ignore during bot speech; reset buffer in LISTEN |
| `_on_user_stopped_speaking()` | VAD | Transition to VALIDATE if in LISTEN state |
| `_on_transcript()` | `TranscriptionFrame` | Accumulate transcript; check user_done, threshold or timer |
| `_validate_response()` | Internal | Word-by-word comparison, save round, transition |
| `_on_round_pass()` | Perfect | +score, advance round, announce next words |
| `_on_retry()` | Partial | Feedback, re-announce words, retry |
| `_on_game_over()` | Exhausted | Say final score, end session, push EndFrame |
| `_on_game_won()` | All rounds done | Congratulations, end session, push EndFrame |
| `_say(text)` | Internal | Push `TTSSpeakFrame` with bot speech |

### State Machine

```python
class GameState(str, Enum):
    IDLE = "idle"
    START_GAME = "start_game"
    SPEAK_SEQUENCE = "speak_sequence"
    LISTEN = "listen"
    VALIDATE = "validate"
    ROUND_PASS = "round_pass"
    GAME_OVER = "game_over"
    ENDED = "ended"
```

---

## 11. Prompt Templates & Random Selection

The LLM is replaced with a **PromptTemplateSelector** with categorized lists of pre-written templates.

### Template Categories

| Category | Trigger | Example |
|----------|---------|---------|
| `start` | Game begins | "Welcome to the Memory Host, {player_name}..." |
| `round_intro` | New round | "Round {round_number}. Here are your words." |
| `success` | Correct answer | "That's correct! Moving to round {round_number}." |
| `failure` | Wrong answer (final) | "Oh, that's not quite right. The correct sequence was..." |
| `retry` | Partial match | "Good try! You got {correct_count} out of {total} correct." |
| `game_over` | Game won | "That's the game! You've completed all rounds." |
| `interrupt` | User interrupts | "Oh, you cut me off! Go ahead, I'm listening." |
| `waiting` | No response | "Take your time, I'm listening..." |

### Selection

1. Game event occurs → `prompt_selector.get("category", **kwargs)`
2. Random template selected from category
3. Template variables `{player_name}`, `{score}`, etc. filled in
4. Formatted text pushed as `TTSSpeakFrame` → TTS → audio

---

## 12. Frontend Architecture (Next.js)

### Pages & Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `HomePage` | Landing + create session form |
| `/game/[sessionId]` | `GamePage` | Game room with WebRTC + game state |
| `/leaderboard` | `LeaderboardPage` | Top 3 scores table |

### Component Tree

```
<Layout>
  ├── <HomePage>
  │   ├── PlayerNameForm
  │   └── Start Game button → POST /api/sessions
  │
  ├── <GamePage>
  │   ├── <GameHeader> (score, round, status)
  │   ├── <WebRTCRoom> (WebRTC + recording controls)
  │   ├── <RoundHistory> (fetches rounds, renders GameLog)
  │   └── <GameOverModal> (score, Play Again, Leaderboard)
  │
  └── <LeaderboardPage>
      └── <LeaderboardTable> (top 3 ranked sessions)
```

### Key Hooks

| Hook | Purpose | Poll Interval |
|------|---------|---------------|
| `useGameState` | Poll `/api/sessions/{id}` | 2s (stops on non-active) |
| `useLeaderboard` | Fetch `/api/leaderboard` | 30s auto-refresh |

---

## 13. Interruption Handling

The bot ignores user speech during its own speech phases to prevent overlapping audio:

1. **During `SPEAK_SEQUENCE` or `ROUND_PASS`** — User speech is silently ignored. The bot continues speaking uninterrupted.
2. **During `_announcing_phase`** — Welcome + initial round announcement is protected.
3. **During `LISTEN`** — User speech resets the transcript buffer for fresh capture.
4. **Transcripts accumulate across states** — If user speaks during bot speech, their words are captured and available when the bot transitions to LISTEN.
5. **Pipeline stops on game over** — `EndFrame` ensures the voicebot doesn't continue playing in the background.

---

## 14. Double-Scoring Prevention

Three-layer protection:

| Layer | Mechanism | Scope |
|-------|-----------|-------|
| 1. In-memory | `self.game.is_validating` guard | Prevents re-entry during async validation |
| 2. DB constraint | `UNIQUE(session_id, round_number)` | Database-level uniqueness |
| 3. App-level | `_check_already_scored()` | Queries DB for existing response |

---

## 15. Retry & Scoring System

### Flow

1. User speaks words → validation compares word-by-word
2. **Perfect match** → `_on_round_pass()`: +score, advance to next round
3. **Partial match, retries left** → `_on_retry()`:
   - Bot gives feedback ("X out of Y correct")
   - Bot re-announces words individually
   - Bot says "Go ahead and repeat that back"
   - 5-second pause → LISTEN
   - Best retry score tracked in `best_retry_count` + `best_retry_words`
4. **All retries exhausted** → `_on_game_over()`:
   - Best retry score applied to total
   - Round saved to DB with best retry words
   - Bot says failure prompt + final score
   - `_end_session()` → DB status = `completed`
   - `EndFrame` pushed → pipeline stops cleanly
5. **Frontend** polls → sees `status !== "active"` → shows `GameOverModal`

### Scoring

- Each correctly matched word = 1 point
- Round score = `correct_count` (number of words matched at correct position)
- Total score = sum of all round scores
- Best retry score applied on game over

---

## 16. Push-to-Talk Recording

### Flow

1. User taps **Start Recording** → mic opens, bot receives audio
2. User speaks words into mic
3. User taps **Stop Recording** → `user_done` message sent via signaling WebSocket
4. Game processor receives `user_done` → triggers validation

### Three-layer Validation Trigger

| Layer | Mechanism | Details |
|-------|-----------|---------|
| 1. Push-to-talk | `user_done_event` | User clicks Stop → immediate validation |
| 2. Inline threshold | Transcript count | >= 5 fragments triggers validation |
| 3. Timer fallback | 4-second silence | Background task triggers after no new transcripts |

### Recording Button

Visual feedback via animated sound wave bars (CSS `waveBar` animation):
- Shows 12 vertical bars with staggered animation delays
- Bars scale up/down in a waveform pattern during recording
- Uses CSS `scaleY` transform for GPU-accelerated animation

---

## 17. Implementation Roadmap

### Phase 1 — ✅ Core Infrastructure
- [x] PostgreSQL setup
- [x] SQLAlchemy models (sessions, rounds)
- [x] FastAPI REST API (sessions, leaderboard, health)
- [x] WebSocket signaling server (port 3001)
- [x] Pipecat pipeline assembly (STT → GameProcessor → TTS)
- [x] In-memory cache (TTLCache)
- [x] Two-service architecture (REST API + Game Engine)

### Phase 2 — ✅ Game Logic
- [x] State machine (IDLE → START → SPEAK → LISTEN → VALIDATE → ...)
- [x] Word sequence generation per round
- [x] Word-by-word validation (pure Python)
- [x] Partial scoring (each correct word = 1 point)
- [x] Retry system (3 retries per round, best score saved)
- [x] Double-scoring prevention (3 layers)
- [x] Prompt template system (random selection, no LLM)

### Phase 3 — ✅ Frontend
- [x] Landing page with name input
- [x] Game room with WebRTC audio
- [x] Push-to-talk recording (Start/Stop button)
- [x] Animated sound wave visualization
- [x] Game state polling (2s interval)
- [x] Round history display
- [x] Game over modal with stats + buttons
- [x] Leaderboard page (top 3 sessions)

### Phase 4 — ✅ Voice Experience
- [x] British English voice (aura-2-pandora-en)
- [x] 10% slower TTS speed (speed=0.9)
- [x] 1-second pauses between words
- [x] Individual word announcements ("Word 1: apple.")
- [x] 5-second processing pauses before listening
- [x] `TTSSpeakFrame` for proper audio context lifecycle
- [x] `EndFrame` push to stop pipeline on game over

---

## 18. Logging

Both services log to:
- **stdout** (colored, development-friendly)
- **`app.log`** (single file at project root, appended on each run, cleared on `./run.sh`)

---

See [README.md](README.md) for full setup instructions.
