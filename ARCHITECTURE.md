# The Memory Host — Architecture & Data Flow

## Overview

The Memory Host is a **voice-based memory card game**. A bot speaks a sequence of words aloud, the player repeats them back from memory, and each correct round adds one more word to the sequence (Round 1 = 1 word, Round 10 = 10 words). The game uses **WebRTC** for real-time voice communication, **Deepgram** for speech-to-text (STT) and text-to-speech (TTS), and **Pipecat** as the AI voice pipeline framework.

---

## The 4 Servers (Port Map)

| Port | Service | Role |
|------|---------|------|
| **5432** | PostgreSQL | Shared database (Docker: `memory-host-db`) |
| **8000** | REST API (FastAPI) | Session CRUD, leaderboard, health — the "backend for the frontend" |
| **3001** | Signaling Server (WebSocket) | SmallWebRTC signaling — relays SDP offers/answers & ICE candidates between bot ↔ client |
| **3002** | Game Engine (FastAPI) | Boots the Pipecat voice bot per session, hosts the signaling server |
| **3000** | Frontend (Next.js) | UI layer (landing page, game page, leaderboard) |

> **Important:** Ports 3001 and 3002 are **both part of the Game Engine** service. The `backend/game-engine/` app is a single Python process that starts two sub-servers:
> - A WebSocket signaling server on **port 3001** (via `websockets.serve`)
> - A FastAPI HTTP server on **port 3002** (for `/start-session` and `/health`)
>
> Both are started/lifecycled together via FastAPI's `lifespan` mechanism in `backend/game-engine/app/main.py`.

---

## Why 4 Servers? — Separation of Concerns

1. **REST API (8000)** — Handles all CRUD operations (create sessions, fetch session state, end sessions, leaderboard). Has **no** voice/AI logic. Could be replaced/swapped without touching the game logic.

2. **Signaling Server (3001)** — A lightweight WebSocket relay for WebRTC connection negotiation. Has **no** game logic. Just relays SDP offers/answers and ICE candidates between exactly 2 peers (bot + client) in a room.

3. **Game Engine (3002)** — The brain. Receives "start session" requests from the REST API, then boots a **Pipecat pipeline** per session that:
   - Connects to the signaling server as the "bot" peer
   - Runs Deepgram STT (speech-to-text) on user audio
   - Runs the `MemoryGameProcessor` (the game logic)
   - Runs Deepgram TTS (text-to-speech) to speak back to the user
   - Writes scores/rounds directly to PostgreSQL

4. **Frontend (3000)** — Next.js app with BFF (Backend-for-Frontend) proxy pattern. All API calls from the browser go to `/api/*` on the same origin, which Next.js proxies to the REST API (port 8000). This keeps backend URLs and API keys server-side.

> **Why split REST API from Game Engine?** The REST API is stateless and lightweight — it can scale independently. The Game Engine is stateful (each bot is a long-running Pipecat pipeline) and resource-heavy (WebRTC + STT + TTS). If the game engine crashes, the REST API still serves session data and leaderboard. If the REST API restarts, active game sessions keep running.

---

## End-to-End Flow

### 1. Player Lands on Home Page

```
Browser  ──GET /──>  Next.js (3000)  ──>  Renders app/page.tsx
```

**Files involved:**
- `frontend/app/page.tsx` — Shows the landing page with name input form
- `frontend/app/layout.tsx` — Root layout with nav bar & background gradients
- `frontend/components/PlayerNameForm.tsx` — Reusable name input component

**Functions called:**
- `HomePage` / `HomePageContent` — renders the hero, form, and feature cards
- `handleStartGame()` — on form submit, calls `fetch("/api/sessions", POST)`

---

### 2. Player Submits Name → Create Session

```
Browser                    Next.js (3000)              REST API (8000)              Game Engine (3002)
  │                             │                            │                            │
  │  POST /api/sessions         │                            │                            │
  │  { player_name: "Alice" }   │                            │                            │
  │────────────────────────────>│                            │                            │
  │                             │                            │                            │
  │                     ┌───────┴───────┐                    │                            │
  │                     │ BFF Proxy     │                    │                            │
  │                     │ route.ts      │                    │                            │
  │                     │ calls         │                    │                            │
  │                     │ createSession()│                   │                            │
  │                     │ from lib/api.ts│                   │                            │
  │                     └───────┬───────┘                    │                            │
  │                             │                            │                            │
  │                             │ POST /api/sessions         │                            │
  │                             │ { player_name: "Alice" }   │                            │
  │                             │───────────────────────────>│                            │
  │                             │                            │                            │
  │                             │              ┌─────────────┴─────────────┐              │
  │                             │              │ create_session()         │              │
  │                             │              │ in routes.py:            │              │
  │                             │              │ 1. Close any existing    │              │
  │                             │              │    active session for    │              │
  │                             │              │    this player (set to   │              │
  │                             │              │    "interrupted")        │              │
  │                             │              │ 2. INSERT new Session    │              │
  │                             │              │    row in PostgreSQL     │              │
  │                             │              │    (status="active")     │              │
  │                             │              │ 3. Generate room name:   │              │
  │                             │              │    memory-game-{8chars}  │              │
  │                             │              │ 4. Fire & forget HTTP    │              │
  │                             │              │    POST to game-engine   │              │
  │                             │              │    /start-session        │              │
  │                             │              └─────────────┬─────────────┘              │
  │                             │                            │                            │
  │                             │                            │  POST /start-session       │
  │                             │                            │  { session_id,             │
  │                             │                            │    player_name }           │
  │                             │                            │───────────────────────────>│
  │                             │                            │                            │
  │                             │                            │              ┌─────────────┴─────────────┐
  │                             │                            │              │ start_session()          │
  │                             │                            │              │ in main.py:              │
  │                             │                            │              │ Fire background task    │
  │                             │                            │              │ create_and_run_bot()   │
  │                             │                            │              │ Return { status: "ok" }│
  │                             │                            │              └─────────────────────────┘
  │                             │                            │                            │
  │                             │  201 { session_id,         │                            │
  │                             │        room_url,           │                            │
  │                             │        room_token, ... }   │                            │
  │                             │<───────────────────────────│                            │
  │                             │                            │                            │
  │  201 { session_id, ... }   │                            │                            │
  │<────────────────────────────│                            │                            │
  │                             │                            │                            │
  │ Store room_url, room_token  │                            │                            │
  │ in sessionStorage           │                            │                            │
  │                             │                            │                            │
  │ Navigate to /game/{id}      │                            │                            │
  │───────────────────────────────────────────────────────────────────────────────────────>
```

**Files involved:**
- `frontend/app/api/sessions/route.ts` — BFF proxy: `POST` handler
- `frontend/lib/api.ts` — `createSession()` — calls REST API at `http://localhost:8000/api/sessions`
- `backend/rest-api/app/api/routes.py` — `create_session()` — the main handler
- `backend/rest-api/app/api/main.py` — FastAPI app entry, CORS setup
- `backend/rest-api/app/api/schemas.py` — `CreateSessionRequest`, `CreateSessionResponse`
- `backend/rest-api/app/api/deps.py` — `DbSession` type alias, `get_db_session()` dependency
- `backend/rest-api/app/models/session.py` — `Session` SQLAlchemy model
- `backend/rest-api/app/core/config.py` — `Settings.GAME_ENGINE_URL = "http://localhost:3002"`
- `backend/game-engine/app/main.py` — `start_session()` — receives the notification, fires bot in background

**Key functions:**
- `create_session()` (routes.py:36-100):
  1. Checks for existing active session → marks as "interrupted"
  2. Creates new `Session` row with status="active", score=0, current_round=0
  3. Generates room name `memory-game-{session_id[:8]}`
  4. Calls `_notify_game_engine()` as a background asyncio task → POST to game-engine
  5. Returns session info + room_url to frontend

---

### 3. Game Engine Boots the Voice Bot

```
Game Engine (3002)
  │
  │  create_and_run_bot() in bot.py
  │
  ├── 1. Create SmallWebRTCConnection (with Google STUN server)
  │
  ├── 2. Create GameData (session_id, player_name, max_rounds)
  │
  ├── 3. Create SignalingClient (connects to ws://localhost:3001/room/{room_name})
  │     │
  │     ├── connect() — WebSocket to signaling server (retries with backoff)
  │     │
  │     └── negotiate() — handles SDP offer/answer exchange:
  │          1. Send { type: "join", kind: "bot" } to signaling server
  │          2. Wait for client's SDP offer (relayed by signaling)
  │          3. Call webrtc_connection.initialize(offer_sdp, "offer")
  │          4. Send SDP answer back via signaling
  │          5. Exchange ICE candidates
  │
  ├── 4. Create SmallWebRTCTransport (with SileroVAD for voice activity detection)
  │
  ├── 5. Create DeepgramSTTService (model="nova-2")
  │
  ├── 6. Create SlowerDeepgramTTSService (voice="aura-2-pandora-en", speed=0.9)
  │     └── Uses HTTP-based TTS (not WebSocket) for speed control support
  │
  ├── 7. Create MemoryGameProcessor (the core game logic)
  │     └── Receives GameData, db_session, cache, prompt_selector
  │
  ├── 8. Assemble Pipecat Pipeline:
  │       transport.input() → stt → game_processor → tts → transport.output()
  │
  └── 9. Run pipeline (await runner.run(task))
```

**Files involved:**
- `backend/game-engine/app/services/bot.py` — `create_and_run_bot()`, `SignalingClient`
- `backend/game-engine/app/services/custom_tts.py` — `SlowerDeepgramTTSService` (extends `DeepgramHttpTTSService`)
- `backend/game-engine/app/signaling/server.py` — `handle_connection()`, `Room`, `RoomManager`
- `backend/game-engine/app/core/cache.py` — `GameCache` (per-process in-memory cache)
- `backend/game-engine/app/core/config.py` — `Settings` (Deepgram key, signaling URL, etc.)
- `backend/game-engine/app/db/database.py` — `async_session_factory` (separate from REST API's DB connection)

---

### 4. Frontend Connects to Voice Room (WebRTC Handshake)

```
Browser (Game Page)         Signaling Server (3001)         Bot (in game-engine)
      │                             │                             │
      │  ws://localhost:3001/room/  │                             │
      │  memory-game-{id}          │                             │
      │────────────────────────────>│                             │
      │                             │                             │
      │  { type: "join",           │                             │
      │    kind: "receiver" }       │                             │
      │────────────────────────────>│                             │
      │                             │                             │
      │              ┌──────────────┴──────────┐                  │
      │              │ Room now has 2 peers:   │                  │
      │              │ bot_ws + client_ws       │                  │
      │              │ Room is FULL →           │                  │
      │              │ signal client to         │                  │
      │              │ create SDP offer         │                  │
      │              └──────────────┬──────────┘                  │
      │                             │                             │
      │  { type: "create_offer" }  │                             │
      │<────────────────────────────│                             │
      │                             │                             │
      │  pc.createOffer()           │                             │
      │  pc.setLocalDescription()   │                             │
      │                             │                             │
      │  { type: "offer",          │                             │
      │    sdp: ... }               │                             │
      │────────────────────────────>│                             │
      │                             │   { type: "offer", sdp }   │
      │                             │───────────────────────────>│
      │                             │                             │
      │                             │              ┌─────────────┴─────────────┐
      │                             │              │ webrtc_connection        │
      │                             │              │ .initialize(sdp,"offer") │
      │                             │              │ → sets remote desc      │
      │                             │              │ → creates SDP answer     │
      │                             │              │ → stores answer          │
      │                             │              └─────────────┬─────────────┘
      │                             │                             │
      │                             │   { type: "answer",        │
      │                             │     sdp: ... }              │
      │                             │<───────────────────────────│
      │  { type: "answer", sdp }   │                             │
      │<────────────────────────────│                             │
      │                             │                             │
      │  pc.setRemoteDescription()  │                             │
      │                             │                             │
      │  ← bidirectional ICE candidates exchanged →              │
      │                             │                             │
      │  ═══════════════════════════════════════════              │
      │  ║  WebRTC Connection Established!        ║              │
      │  ║  User mic → bot (STT)                 ║              │
      │  ║  Bot TTS → user speakers              ║              │
      │  ═══════════════════════════════════════════              │
```

**Files involved:**
- `frontend/components/WebRTCRoom.tsx` — The entire WebRTC client implementation
- `frontend/app/game/[sessionId]/page.tsx` — Game page, orchestrates WebRTCRoom + polling
- `frontend/hooks/useGameState.ts` — Polls REST API every 2s for session state
- `frontend/hooks/useLeaderboard.ts` — Fetches leaderboard (used on leaderboard page)

**Key functions in `WebRTCRoom.tsx`:**
- Creates `RTCPeerConnection` with Google STUN server
- `pc.addTransceiver("audio", { direction: "sendrecv" })` — bidirectional audio
- `navigator.mediaDevices.getUserMedia({ audio })` — captures mic
- Connects WebSocket to signaling server, sends join message
- On `create_offer` → creates SDP offer, sends to signaling
- On `answer` → sets remote description (bot's answer)
- On `ice-candidate` → adds to peer connection
- **Push-to-talk**: mic is disabled by default `setMicEnabled(false)`. User taps "Start Recording" → mic enabled. User taps "Stop" → mic disabled + sends `{ type: "user_done" }` to bot via signaling.
- Listens for `bot-stopped-speaking` on data channel to know when game over audio finished

---

### 5. Game Flow (Inside MemoryGameProcessor)

```
MemoryGameProcessor STT ──> MemoryGameProcessor ──> TTS
                              │
                    GameState Machine:
                    ┌────────────────────────────────────────────┐
                    │                                            │
                    │  IDLE ──> START_GAME                       │
                    │              │                             │
                    │              ▼                             │
                    │         SPEAK_SEQUENCE  ◄──────┐           │
                    │              │                  │          │
                    │              ▼                  │          │
                    │            LISTEN               │          │
                    │              │                  │          │
                    │              ▼                  │          │
                    │          VALIDATE               │          │
                    │           /    \                │          │
                    │          ▼      ▼               │          │
                    │    ROUND_PASS  RETRY ───────────┘          │
                    │         │                                  │
                    │         ▼                                  │
                    │     GAME_OVER ──> ENDED                     │
                    │                                            │
                    └────────────────────────────────────────────┘
```

**Files involved:**
- `backend/game-engine/app/services/game_processor.py` — `MemoryGameProcessor` (the core)
- `backend/game-engine/app/services/game_state.py` — `GameData`, `GameState` enum
- `backend/game-engine/app/services/game_logic.py` — `generate_sequence()`, `compare_word_by_word()`, `parse_transcript_to_words()`
- `backend/game-engine/app/services/prompt_templates.py` — `PromptTemplateSelector` (random templates for bot speech)
- `backend/game-engine/app/core/constants.py` — `WORD_POOL` (144 common English words)

**Detailed step-by-step:**

#### 5a. Game Start
1. `_on_start()` is called when `StartFrame` received
2. Resets `GameData` (score=0, round=1)
3. Transitions to `START_GAME` → then `SPEAK_SEQUENCE`
4. Calls `generate_sequence(round_number=1)` — picks 1 random word from WORD_POOL
5. Calls `_say(welcome_prompt)` — speaks welcome message
6. Calls `_announce_round()` — speaks "Round 1. Here are your words. Word 1: apple."
7. Transitions to `LISTEN`
8. Starts `_poll_task` — checks `user_done_event` every 500ms

#### 5b. User Speaks → STT → Transcription
1. User taps "Start Recording" → mic enabled
2. User speaks words → audio flows through WebRTC → bot receives
3. `DeepgramSTTService` transcribes audio → emits `TranscriptionFrame`s
4. `MemoryGameProcessor._on_transcript()` accumulates text in `user_transcript_buffer`
5. Three ways validation triggers:
   - **Layer 1 (Push-to-talk)**: User taps "Stop" → `user_done` signal sent via signaling → `user_done_event.set()` → triggers validation
   - **Layer 2 (Threshold)**: Buffer size >= max(5, expected_words+2) → triggers validation
   - **Layer 3 (Timer)**: 4 seconds of silence → triggers validation

#### 5c. Validation
1. `_validate_response()` called:
   - Sets `is_validating = True` (prevents double-scoring)
   - `parse_transcript_to_words(buffer)` → flattens all transcript fragments into word list
   - `compare_word_by_word(expected, actual)` — case-insensitive, punctuation-stripped comparison
   - Results: `{ correct_count, total, is_perfect, details }`

2. **If PERFECT:**
   - `_save_round_to_db()` — inserts round into PostgreSQL via game-engine's DB connection
   - `_on_round_pass()` — adds score, advances `current_round`, generates new sequence
   - `_update_db_session()` — writes score + round to PostgreSQL (so REST API can read it)
   - `_update_cache()` — updates in-memory cache, invalidates leaderboard cache
   - Speaks congratulation + new words → transitions to `LISTEN`

3. **If PARTIAL + retries remaining:**
   - `_on_retry()` — tracks best attempt, decrements `retries_remaining`
   - Speaks feedback + re-announces same words → transitions to `LISTEN`

4. **If NO retries left:**
   - `_on_game_over()` — uses best retry attempt, saves to DB
   - Speaks failure message with correct sequence + final score
   - Calls `_end_session()` — marks session as "completed" in DB
   - Pushes `EndFrame()` to stop pipeline

5. **If all rounds completed:**
   - `_on_game_won()` — congratulates, calls `_end_session()`, pushes `EndFrame()`

#### 5d. Game End Cleanup (in `create_and_run_bot()` finally block)
- Cancels SDP negotiation task
- Closes signaling WebSocket
- Closes aiohttp session
- Commits any pending DB changes
- If session still "active" with score > 0, marks as "completed"

---

### 6. Frontend Polling & Game Over

```
Browser (Game Page)              Next.js BFF              REST API (8000)
      │                             │                          │
      │  ──[every 2s]──             │                          │
      │  GET /api/sessions/{id}      │                          │
      │────────────────────────────>│                          │
      │                             │  GET /api/sessions/{id}  │
      │                             │─────────────────────────>│
      │                             │                          │
      │                             │  ┌───────────────────────┴──────┐
      │                             │  │ get_session() routes.py:    │
      │                             │  │ SELECT from PostgreSQL      │
      │                             │  │ (reads score, round, status)│
      │                             │  └───────────────────────┬──────┘
      │                             │                          │
      │  { status, score,           │                          │
      │    current_round, ... }      │                          │
      │<────────────────────────────│                          │
      │                             │                          │
      │  ──[Game Over conditions]──                              │
      │  When BOTH are true:                                    │
      │  1. isGameOver = (status !== "active")                  │
      │  2. botStoppedSpeaking = true (from data channel)       │
      │                                                         │
      │  ──> Show GameOverModal                                 │
```

**Files involved:**
- `frontend/hooks/useGameState.ts` — `useGameState(sessionId, 2000)` — polls every 2s
- `frontend/app/api/sessions/[id]/route.ts` — BFF proxy for `GET /api/sessions/{id}`
- `backend/rest-api/app/api/routes.py` — `get_session()` — reads from PostgreSQL
- `frontend/components/GameOverModal.tsx` — shown when game ends
- `frontend/app/game/[sessionId]/page.tsx` — orchestrates polling + game over logic

---

### 7. Leaderboard

```
Browser                    Next.js BFF              REST API (8000)
  │                             │                          │
  │  GET /api/leaderboard       │                          │
  │────────────────────────────>│                          │
  │                             │  GET /api/leaderboard    │
  │                             │─────────────────────────>│
  │                             │                          │
  │                             │  ┌───────────────────────┴──────────┐
  │                             │  │ get_leaderboard() routes.py:     │
  │                             │  │ SELECT top 3 sessions            │
  │                             │  │ WHERE status IN                  │
  │                             │  │  ("completed","interrupted")     │
  │                             │  │   AND score > 0                  │
  │                             │  │ ORDER BY score DESC,             │
  │                             │  │   current_round DESC,            │
  │                             │  │   created_at ASC                 │
  │                             │  │ LIMIT 3                          │
  │                             │  └───────────────────────┬──────────┘
  │                             │                          │
  │  { leaderboard: [...] }     │                          │
  │<────────────────────────────│                          │
```

**Files involved:**
- `frontend/app/leaderboard/page.tsx` — Leaderboard page
- `frontend/hooks/useLeaderboard.ts` — `useLeaderboard(30000)` — auto-refreshes every 30s
- `frontend/app/api/leaderboard/route.ts` — BFF proxy
- `frontend/components/LeaderboardTable.tsx` — Renders the table with 🥇🥈🥉
- `backend/rest-api/app/api/routes.py` — `get_leaderboard()`

---

## Voice Data Flow — Audio Pipeline Deep Dive

This section explains **how audio moves through the system**: from the user's microphone, through
the network and backend pipeline, to Deepgram for transcription and back again as synthesized
speech. This is the most critical data path in the application.

### High-Level Audio Path

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                        END-TO-END AUDIO FLOW                                  │
│                                                                                │
│  User Mic                                                      User Speakers   │
│    │                                                               ▲           │
│    │ getUserMedia({ audio })                                      │           │
│    ▼                                                               │           │
│  ┌──────────────┐          ┌──────────────────┐          ┌──────────────┐      │
│  │ Browser      │  SRTP    │  Bot Peer        │  SRTP    │ Browser      │      │
│  │ SEND track   │ ──────►  │  (Game Engine)   │ ──────►  │ RECV track   │      │
│  │ (mic audio)  │          │                   │          │ (TTS audio)  │      │
│  └──────┬───────┘          └───────┬───────────┘          └──────▲───────┘      │
│         │                          │                             │              │
│         │                   Pipecat Pipeline                     │              │
│         │                  ┌─────────────────┐                  │              │
│         │                  │                 │                  │              │
│         └──────────────────► STT Service     │                  │              │
│                            │ (Deepgram       │                  │              │
│                            │  Nova-2)        │                  │              │
│                            │       │         │                  │              │
│                            │       ▼         │                  │              │
│                            │ Transcription   │   ┌──────────────┘              │
│                            │ Frame           │   │                            │
│                            │       │         │   │                            │
│                            │       ▼         │   │                            │
│                            │ MemoryGame      │   │                            │
│                            │ Processor       │   │                            │
│                            │ (game logic)    │───┤                            │
│                            │       │         │   │                            │
│                            │       ▼         │   │                            │
│                            │ TTSSpeakFrame   │   │                            │
│                            │       │         │   │                            │
│                            │       ▼         │   │                            │
│                            │ TTS Service     │───┘                            │
│                            │ (Deepgram       │                                │
│                            │  Aura 2 Pandora)│                                │
│                            │                 │                                │
│                            └─────────────────┘                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

### Step 1: User Microphone Capture (Frontend)

**File:** `frontend/components/WebRTCRoom.tsx`

```typescript
// 1. Create RTCPeerConnection with Google's public STUN server
const pc = new RTCPeerConnection({
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
});

// 2. Explicitly add a sendrecv audio transceiver BEFORE getUserMedia.
//    This signals the SDP offer that the browser wants to BOTH send
//    audio TO the bot AND receive audio FROM the bot.
//    Without this, the default direction is "sendonly" and the bot's
//    TTS audio never reaches the user.
pc.addTransceiver("audio", { direction: "sendrecv" });

// 3. Capture the user's microphone with audio processing enabled
const userStream = await navigator.mediaDevices.getUserMedia({
  audio: {
    echoCancellation: true,   // Cancel echo from speakers
    noiseSuppression: true,   // Reduce background noise
    autoGainControl: true,    // Normalize volume
  },
});

// 4. Add all audio tracks from the stream to the peer connection.
//    Because a sendrecv transceiver already exists for "audio",
//    addTrack() reuses it instead of creating a duplicate.
for (const track of userStream.getAudioTracks()) {
  pc.addTrack(track, userStream);
}
userTracksRef.current = userStream.getAudioTracks();

// 5. Start with mic DISABLED (push-to-talk model).
//    The user taps "Start Recording" to enable, "Stop" to disable.
setMicEnabled(false);
```

**Key details:**
- The mic is captured via browser's standard `getUserMedia` API
- Three audio processing flags (`echoCancellation`, `noiseSuppression`, `autoGainControl`) are enabled to improve audio quality
- The transceiver direction is **explicitly** set to `sendrecv` — this is critical. Without it, the default is `sendonly`, and the bot's TTS audio output would never reach the browser
- **Push-to-talk**: the user's mic tracks are disabled by default (`track.enabled = false`). When the user taps "Start Recording", `setMicEnabled(true)` enables all tracks, and the browser starts sending audio. When tapped "Stop", `setMicEnabled(false)` disables them

---

### Step 2: Audio Travels Over WebRTC (Browser → Backend)

The browser's `RTCPeerConnection` wraps the raw PCM audio frames from the microphone
into **SRTP (Secure Real-time Transport Protocol)** packets and sends them to the bot
peer (running in the Game Engine process).

The path:

```
Browser RTCPeerConnection (SEND track)
        │
        │ SRTP packets over UDP (ICE-negotiated path)
        │ Google STUN server used for NAT traversal
        ▼
Bot's SmallWebRTCConnection (Pipecat)
        │
        │ Audio frames decoded from SRTP
        ▼
SmallWebRTCTransport.input()
        │
        │ Frames enter the Pipecat pipeline
        ▼
SileroVADAnalyzer (Voice Activity Detection)
  • confidence: 0.5     — Lower threshold catches quieter speech
  • start_secs: 0.3     — Longer start avoids clipping first syllables
  • stop_secs: 0.5      — Longer stop avoids cutting mid-sentence
  • min_volume: 0.3     — Lower threshold catches softer voices
  • vad_audio_passthrough: true  — Audio continues through pipeline even
                                   when VAD is not actively detecting speech
```

**Why STUN and not TURN?** Both peers are expected to be on networks that
support direct UDP connectivity. The Google STUN server (`stun:stun.l.google.com:19302`)
helps each peer discover its public IP and port. If a symmetric NAT were present,
a TURN server would be needed, but for local development this is not required.

---

### Step 3: Speech-to-Text via Deepgram Nova-2

**File:** `backend/game-engine/app/services/bot.py` (line ~160)

```python
stt = DeepgramSTTService(
    api_key=api_key,
    model="nova-2",          # Deepgram's most accurate general-purpose model
    sample_rate=16000,       # 16kHz sample rate (standard for voice)
)
```

Once the raw audio frames enter the Pipecat pipeline from `SmallWebRTCTransport.input()`,
they flow into `DeepgramSTTService`. This service:

1. Opens a **WebSocket connection** to Deepgram's real-time STT API
   (`wss://api.deepgram.com/v1/listen`)
2. Streams audio chunks to Deepgram as they arrive from WebRTC
3. Deepgram processes the audio and returns **interim** (partial) and **final** transcriptions
4. The service emits `TranscriptionFrame` objects into the pipeline for each transcript result

```
Raw audio frames (16000 Hz, linear16)
        │
        ▼
DeepgramSTTService
  ┌───────────────────────────────────────────┐
  │  WebSocket → wss://api.deepgram.com/       │
  │  /v1/listen                                │
  │                                           │
  │  Sends: raw audio chunks                  │
  │  Receives: JSON transcript results         │
  │    { type: "Results",                      │
  │      channel: { alternatives: [            │
  │        { transcript: "apple banana cat" }  │
  │      ]}                                    │
  │    }                                       │
  │                                           │
  │  Output: TranscriptionFrame(text)          │
  └──────────────┬────────────────────────────┘
                 │
                 ▼
          MemoryGameProcessor
          (game logic)
```

---

### Step 4: Transcript Accumulation & Validation Trigger

**File:** `backend/game-engine/app/services/game_processor.py`

`TranscriptionFrame`s arrive at `MemoryGameProcessor._on_transcript()` and are
accumulated in `game.user_transcript_buffer`:

```python
async def _on_transcript(self, frame: TranscriptionFrame) -> None:
    now = time.monotonic()
    self._last_transcript_time = now
    self.game.user_transcript_buffer.append(frame.text)
    # Buffers accumulate interim + final transcripts
    # e.g. ["I", "I said", "I said apple", "apple", "apple banana"]
```

Validation is triggered by **three independent layers**:

| Layer | Trigger | Mechanism | Reliability |
|-------|---------|-----------|-------------|
| **1. Push-to-talk (PTT)** | User taps "Stop Recording" → `{ type: "user_done" }` sent via signaling WebSocket → relayed by signaling server to bot → `user_done_event.set()` | Most explicit — user says "I'm done" | 🟢 **Highest** |
| **2. Transcript threshold** | Buffer size >= max(5, expected_words + 2) | Fires during active speech when enough fragments accumulate | 🟡 Medium |
| **3. Silence timer** | 4 seconds after last `TranscriptionFrame` with no new speech | Background asyncio task, cancelled/restarted on each transcript | 🟠 Fallback |

```
┌─────────────────────────────────────────────────────┐
│             THREE-LAYER VALIDATION ENGINE            │
│                                                     │
│  Layer 1: user_done_event (PTT)                     │
│  ─────────────────────────────────────               │
│  User taps Stop → signaling relays "user_done"      │
│  → SignalingClient receives → sets event            │
│  → Poll task (500ms) or _on_transcript checks        │
│  → Validates immediately                            │
│                                                     │
│  Layer 2: Transcript threshold                       │
│  ────────────────────────────────                    │
│  Buffer >= max(5, expected+2) → immediate validate  │
│                                                     │
│  Layer 3: 4-second timer                            │
│  ─────────────────────────────                       │
│  User stops speaking → VAD fires                    │
│  UserStoppedSpeakingFrame → validate                 │
│  OR: no transcripts for 4s → timer fires → validate │
└─────────────────────────────────────────────────────┘
```

---

### Step 5: Text-to-Speech via Deepgram Aura 2 (HTTP)

**Files:**
- `backend/game-engine/app/services/game_processor.py` — `_say()` method
- `backend/game-engine/app/services/custom_tts.py` — `SlowerDeepgramTTSService`

When the game processor wants the bot to speak, it pushes a `TTSSpeakFrame`:

```python
async def _say(self, text: str) -> None:
    # Uses TTSSpeakFrame, NOT TextFrame!
    # TTSSpeakFrame triggers proper audio context lifecycle
    await self.push_frame(TTSSpeakFrame(text=text))
```

`TTSSpeakFrame` is critical because it triggers `on_turn_context_completed()`
in Pipecat's TTS pipeline, which appends a `None` sentinel to the context queue.
`TextFrame` does NOT trigger this — causing the TTS to silently drop audio.

**The TTS HTTP request:**

```python
# SlowerDeepgramTTSService builds this request:

POST https://api.deepgram.com/v1/speak
Headers:
  Authorization: Token {DEEPGRAM_API_KEY}
  Content-Type: application/json

Query params:
  model: aura-2-pandora-en    # British English voice
  encoding: linear16           # Uncompressed PCM
  sample_rate: 16000           # 16kHz
  container: none              # Raw audio streaming (no WAV/MP3 wrapper)
  speed: 0.9                   # 10% slower than normal for clarity

Body:
  { "text": "Round 1. Here are your words." }
```

**Why HTTP instead of WebSocket for TTS?** Deepgram's WebSocket TTS endpoint
does NOT support the `speed` parameter — it rejects it with HTTP 400. The HTTP
`/v1/speak` endpoint does support `speed` (range 0.7–1.5). The HTTP service streams
audio chunks progressively as they arrive from Deepgram (`async for chunk in response.content.iter_chunked(CHUNK_SIZE)`), so the latency difference vs WebSocket
is minimal (~200–500ms TTFB).

---

### Step 6: TTS Audio Returns to User (Backend → Browser)

```
Deepgram TTS HTTP Response
  │
  │ Audio chunks streamed as raw linear16 PCM
  │ (no container wrapping — "container": "none")
  ▼
SlowerDeepgramTTSService.run_tts()
  │
  │ Yields TTSAudioRawFrame for each chunk
  │   { audio: bytes, sample_rate: 16000, num_channels: 1 }
  ▼
Pipeline pushes TTSAudioRawFrame through
  │
  ▼
SmallWebRTCTransport.output()
  │
  │ Encodes audio into WebRTC SRTP packets
  ▼
Bot's SmallWebRTCConnection
  │
  │ SRTP over UDP (same ICE-negotiated path as input)
  ▼
Browser RTCPeerConnection
  │
  │ ontrack fires with audio MediaStreamTrack
  ▼
Hidden <audio ref={audioRef} autoPlay />
  │
  │ Audio track added to stream → browser decodes → plays
  ▼
User hears bot's voice through speakers 🎧
```

**Frontend code** (WebRTCRoom.tsx):
```typescript
pc.ontrack = (event) => {
  if (event.track.kind === "audio" && audioRef.current) {
    const stream = audioRef.current.srcObject;
    if (stream instanceof MediaStream) {
      stream.addTrack(event.track);  // Add new track to existing stream
    } else {
      const newStream = new MediaStream([event.track]);
      audioRef.current.srcObject = newStream;  // First track — create stream
    }
  }
};
```

The audio element is rendered with `autoPlay` so the browser immediately
starts playing incoming audio without user interaction:

```tsx
<audio ref={audioRef} autoPlay className="hidden" />
```

---

### Step 7: Data Channel — Bot Speech Completion Signal

Beyond audio, the WebRTC connection includes a **data channel** that the bot uses
to send game state updates and lifecycle signals.

**Client-side setup** (WebRTCRoom.tsx):
```typescript
// Create a data channel immediately so the SDP offer includes
// a data m= section. Without this, the bot's data channel
// never opens.
const dc = pc.createDataChannel("game");

dc.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data?.type === "bot-stopped-speaking") {
    // Pipecat sends this RTVI event when TTS finishes
    // playing all audio. This signals the frontend that
    // the bot has finished speaking the game over message.
    onBotFinishedSpeaking?.();
  }
};

// Also listen for bot's data channel
pc.ondatachannel = (event) => {
  const botChannel = event.channel;
  botChannel.onmessage = (msgEvent) => {
    const data = JSON.parse(msgEvent.data);
    if (data?.type === "bot-stopped-speaking") {
      onBotFinishedSpeaking?.();
    }
  };
};
```

**Why this signal matters:** The Game Over modal must only appear AFTER the bot
has finished speaking the final message. The frontend uses a **two-condition gate**:

```typescript
const isGameOver = gameState.status !== "active";  // From polling DB
const showGameOver = isGameOver && botStoppedSpeaking;  // Must also hear bot finish
```

---

### Audio Format Summary

| Stage | Format | Sample Rate | Notes |
|-------|--------|-------------|-------|
| Browser mic capture | Raw PCM (via `getUserMedia`) | Device default (typ. 48kHz) | Browser handles encoding to Opus for WebRTC |
| WebRTC transport | Opus (in SRTP) | 48kHz (Opus default) | Encoded by browser's WebRTC stack |
| Pipecat internal frames | `AudioRawFrame` | 16000 Hz | Resampled by `SmallWebRTCTransport` |
| Deepgram STT input | PCM audio (via WebSocket) | 16000 Hz | Sent in chunks from `DeepgramSTTService` |
| Deepgram TTS output | linear16 PCM | 16000 Hz | Raw audio, no container (container=none) |
| WebRTC output | Opus (in SRTP) | 48kHz | Encoded by `SmallWebRTCTransport.output()` |
| Browser playback | Decoded PCM | Device native | `HTMLAudioElement` with `autoPlay` |

---

### Word-by-Word Announcement with Pauses

When the bot announces the word sequence (either the initial round announcement
or a retry), each word is spoken **individually** with a 1-second pause:

```python
async def _say_words_with_pauses(self, words: list[str]) -> None:
    """Announce each word individually with a 1-second pause."""
    for i, word in enumerate(words):
        await self._say(f"Word {i + 1}: {word}.")  # Each word = one TTSSpeakFrame
        await asyncio.sleep(1.0)  # 1-second gap between words
```

This cannot be done with a single TTS utterance like "Word 1: apple, Word 2: banana"
because TTS would speak it as a continuous phrase without clear word boundaries.
Each word gets its own `TTSSpeakFrame` with a deliberate `asyncio.sleep(1.0)` gap.

---

### Push-to-Talk Signal Flow (user_done)

The user_done signal travels through a different path than audio:

```
Browser
  │  User taps "Stop Recording"
  │
  │  setMicEnabled(false)     → Disables mic tracks immediately
  │  sendUserDone()            → Sends over signaling WebSocket
  │
  ▼
Signaling Server (3001)
  │  Relays { type: "user_done" } from client_ws → bot_ws
  │
  ▼
SignalingClient.negotiate() (bot.py)
  │  Receives msg.type === "user_done"
  │  Sets game_data.user_done_event.set()
  │
  ▼
MemoryGameProcessor
  │  Two paths check the event:
  │  1. _on_transcript() checks on each new transcript fragment
  │  2. _poll_user_done() checks every 500ms (catches cases
  │     where no transcripts arrive after button release)
  │
  ▼
Validation triggers
```

This separation is intentional: audio and control signals use different channels.
Audio uses WebRTC SRTP (low-latency, high-bandwidth). Control signals use the
signaling WebSocket (reliable, ordered).

---

## Database Schema

### `sessions` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | Auto-generated |
| `player_name` | VARCHAR(100) | |
| `status` | VARCHAR(20) | `active` \| `completed` \| `interrupted` |
| `score` | INTEGER | Default 0 |
| `current_round` | INTEGER | Current round number |
| `max_rounds` | INTEGER | Default 10 |
| `room_url` | TEXT | `http://localhost:3001/room/{name}` |
| `room_name` | VARCHAR(100) | `memory-game-{8chars}` |
| `created_at` | TIMESTAMPTZ | From TimestampMixin |
| `updated_at` | TIMESTAMPTZ | From TimestampMixin |
| `ended_at` | TIMESTAMPTZ | Nullable |

### `rounds` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | |
| `session_id` | UUID (FK → sessions.id) | CASCADE delete |
| `round_number` | INTEGER | 1-indexed |
| `word_sequence` | JSONB | `["apple", "banana", "cat"]` |
| `user_response` | JSONB | Nullable, `["apple", "banana"]` |
| `is_correct` | BOOLEAN | Nullable (null = pending) |
| `answered_at` | TIMESTAMPTZ | Nullable |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**Unique constraint:** `(session_id, round_number)` — prevents double-scoring.

---

## Communication Summary

| From | To | Protocol | When | What |
|------|----|----------|------|------|
| Browser → Next.js | `/api/*` | HTTP | All times | BFF proxy calls |
| Next.js → REST API | `localhost:8000/api/*` | HTTP | Session CRUD, leaderboard | REST calls via `lib/api.ts` |
| REST API → Game Engine | `localhost:3002/start-session` | HTTP (POST) | Session creation | Fire-and-forget to boot bot |
| Bot → Signaling Server | `ws://localhost:3001/room/{id}` | WebSocket | Game start | Bot joins as peer |
| Browser → Signaling Server | `ws://localhost:3001/room/{id}` | WebSocket | Game start | Client joins as peer |
| Browser ↔ Signaling | WebSocket messages | JSON | SDP negotiation | Offers, answers, ICE candidates |
| Browser ↔ Bot | WebRTC (media) | SRTP/SCTP | Game play | Bidirectional audio + data channel |
| Bot → PostgreSQL | `localhost:5432` | SQL (asyncpg) | Scoring | Writes scores, rounds, session status |
| REST API → PostgreSQL | `localhost:5432` | SQL (asyncpg) | Polling/reads | Reads session state, leaderboard |

---

## Data Flow Diagram

```
┌──────────┐    HTTP/3000    ┌──────────────────────────────────────────────┐
│          │ ◄─────────────► │              Next.js Frontend (3000)          │
│  Browser │                 │  ┌───────────┐  ┌───────────┐  ┌──────────┐  │
│          │                 │  │ BFF Proxy  │  │  Pages    │  │  Hooks   │  │
└──────────┘                 │  │ /api/*     │  │ /, /game, │  │ useGame  │  │
     │                       │  │ route.ts   │  │ /leader   │  │ State    │  │
     │ WebSocket (3001)      │  └─────┬─────┘  │ board     │  │ useLead  │  │
     │ WebRTC (media)        │        │         └───────────┘  │ erboard  │  │
     │                       │        │ HTTP                   └──────────┘  │
     │                       └────────┼──────────────────────────────────────┘
     │                                │
     ▼                                ▼  HTTP
┌──────────────────┐        ┌──────────────────┐       ┌──────────────────┐
│ Signaling Server │        │  REST API (8000)  │       │ Game Engine      │
│  (Port 3001)     │        │  FastAPI          │       │  (Port 3002)     │
│                  │        │                   │       │  FastAPI         │
│ Room Manager:    │        │ Routes:           │       │                  │
│  ┌───────────┐   │        │  POST /sessions   │       │ POST /start-     │
│  │ Room A    │   │        │  GET /sessions/   │       │   session        │
│  │  bot_ws   │───┼────────│    {id}           │       │ GET /health      │
│  │  client_ws│   │        │  POST /sessions/  │       │                  │
│  └───────────┘   │        │    {id}/end       │       │ Lifespan starts  │
│                  │        │  GET /sessions/   │       │ signaling server │
│ Relays:          │        │    {id}/rounds    │       │                  │
│  SDP offers      │        │  GET /leaderboard │       │ Background tasks:│
│  SDP answers     │        │  GET /health      │       │  create_and_run_ │
│  ICE candidates  │        │                   │       │  bot()           │
│  user_done       │        │ DB: reads session │       │                  │
│  peer_disconnect │        │    state, leader  │       │ Pipecat Pipeline:│
└──────────────────┘        │    board          │       │  in -> STT ->    │
                             │                   │       │  GameProcessor   │
                             │ Shares PostgreSQL │       │  -> TTS -> out   │
                             │  but has its OWN  │       │                  │
                             │  in-memory cache  │       │ DB: writes scores│
                             └────────┬──────────┘       │    rounds, status│
                                      │                  └────────┬─────────┘
                                      │                           │
                                      ▼                           ▼
                            ┌──────────────────────────────────────────┐
                            │         PostgreSQL (5432)                │
                            │  Docker: memory-host-db                  │
                            │  ┌────────────┐  ┌────────────┐         │
                            │  │ sessions   │  │ rounds     │         │
                            │  │ table      │  │ table      │         │
                            │  └────────────┘  └────────────┘         │
                            └──────────────────────────────────────────┘
```

---

## Key Files Reference

### Backend — REST API (Port 8000)
| File | Purpose |
|------|---------|
| `backend/rest-api/app/api/main.py` | FastAPI app entry, CORS, route registration |
| `backend/rest-api/app/api/routes.py` | All API endpoints: `create_session`, `get_session`, `end_session`, `get_session_rounds`, `get_leaderboard`, `health_check` |
| `backend/rest-api/app/api/schemas.py` | Pydantic request/response models |
| `backend/rest-api/app/api/deps.py` | `DbSession` dependency injection |
| `backend/rest-api/app/core/config.py` | `Settings` — `DATABASE_URL`, `GAME_ENGINE_URL` |
| `backend/rest-api/app/db/database.py` | SQLAlchemy engine + session factory |
| `backend/rest-api/app/models/session.py` | `Session` ORM model |
| `backend/rest-api/app/models/round.py` | `Round` ORM model |
| `backend/rest-api/app/models/base.py` | `Base`, `UUIDMixin`, `TimestampMixin` |

### Backend — Game Engine (Port 3002 + 3001)
| File | Purpose |
|------|---------|
| `backend/game-engine/app/main.py` | FastAPI app entry: `/start-session`, `/health`. Lifespan starts signaling server on 3001. |
| `backend/game-engine/app/signaling/server.py` | WebSocket signaling server. `Room` and `RoomManager` classes. `handle_connection()`, `safe_send()` |
| `backend/game-engine/app/services/bot.py` | `create_and_run_bot()` — assembles the entire Pipecat pipeline. `SignalingClient` — WebSocket client for SDP negotiation. |
| `backend/game-engine/app/services/game_processor.py` | `MemoryGameProcessor` — the core game state machine. `_on_start`, `_on_transcript`, `_validate_response`, `_on_round_pass`, `_on_retry`, `_on_game_over`, `_on_game_won`, `_end_session` |
| `backend/game-engine/app/services/game_state.py` | `GameState` enum (`IDLE`, `START_GAME`, `SPEAK_SEQUENCE`, `LISTEN`, `VALIDATE`, `ROUND_PASS`, `GAME_OVER`, `ENDED`). `GameData` dataclass. |
| `backend/game-engine/app/services/game_logic.py` | `generate_sequence()`, `compare_word_by_word()`, `parse_transcript_to_words()`, `get_words_for_round()` |
| `backend/game-engine/app/services/prompt_templates.py` | `PromptTemplateSelector` — categorized templates for start, round_intro, success, failure, retry, game_over, interrupt, waiting |
| `backend/game-engine/app/services/custom_tts.py` | `SlowerDeepgramTTSService` — HTTP-based TTS with speed control (0.7–1.5) |
| `backend/game-engine/app/core/cache.py` | `GameCache` — per-process TTLCache for sessions, rounds, leaderboard |
| `backend/game-engine/app/core/constants.py` | `WORD_POOL` — 144 common English words |
| `backend/game-engine/app/core/config.py` | `Settings` — `DEEPGRAM_API_KEY`, `DATABASE_URL`, `SMALLWEBRTC_SERVER_URL` |
| `backend/game-engine/app/db/database.py` | Separate SQLAlchemy engine + session factory (same DB as REST API) |
| `backend/game-engine/app/models/session.py` | Duplicated `Session` model (same schema as REST API's) |
| `backend/game-engine/app/models/round.py` | Duplicated `Round` model (same schema) |

### Frontend — Next.js (Port 3000)
| File | Purpose |
|------|---------|
| `frontend/app/page.tsx` | Landing page with name form |
| `frontend/app/game/[sessionId]/page.tsx` | Game page — orchestrates WebRTC + polling + Game Over |
| `frontend/app/leaderboard/page.tsx` | Leaderboard page |
| `frontend/app/layout.tsx` | Root layout, nav, footer |
| `frontend/app/api/sessions/route.ts` | BFF: `POST /api/sessions` |
| `frontend/app/api/sessions/[id]/route.ts` | BFF: `GET /api/sessions/{id}` |
| `frontend/app/api/sessions/[id]/end/route.ts` | BFF: `POST /api/sessions/{id}/end` |
| `frontend/app/api/sessions/[id]/rounds/route.ts` | BFF: `GET /api/sessions/{id}/rounds` |
| `frontend/app/api/leaderboard/route.ts` | BFF: `GET /api/leaderboard` |
| `frontend/components/WebRTCRoom.tsx` | WebRTC client: peer connection, mic, push-to-talk, signaling |
| `frontend/components/GameHeader.tsx` | Score, round progress, status badge |
| `frontend/components/GameOverModal.tsx` | Game over overlay with stats |
| `frontend/components/RoundHistory.tsx` | Polls + renders round history via GameLog |
| `frontend/components/GameLog.tsx` | Renders expected vs actual word comparison |
| `frontend/components/LeaderboardTable.tsx` | Top 3 players with 🥇🥈🥉 |
| `frontend/components/PlayerNameForm.tsx` | Reusable name input form |
| `frontend/components/LoadingSkeleton.tsx` | Loading skeleton (card/text/page variants) |
| `frontend/hooks/useGameState.ts` | `useGameState()` — polls every 2s, auto-stops on game end |
| `frontend/hooks/useLeaderboard.ts` | `useLeaderboard()` — fetches with optional auto-refresh |
| `frontend/lib/api.ts` | All API client functions: `createSession`, `getSession`, `endSession`, `getSessionRounds`, `getLeaderboard`, `healthCheck` |
| `frontend/next.config.ts` | Next.js config |
| `frontend/package.json` | Dependencies (Next.js 15, React 19, Tailwind) |

---

## Interesting Design Decisions

1. **Why duplicated models in REST API and Game Engine?** — Each is a separate Python process with its own SQLAlchemy engine. They share the same PostgreSQL database but have separate connections and connection pools. The models are duplicated to keep each service self-contained and independently deployable.

2. **Two caches, same database** — Both the REST API and Game Engine have separate in-memory `TTLCache` instances. The Game Engine writes scores/rounds directly to PostgreSQL after each round. The REST API reads from PostgreSQL on every poll (with `next: { revalidate: 0 }` to bypass Next.js cache). The Game Engine's cache is used internally (e.g., leaderboard invalidation hints).

3. **Fire-and-forget bot startup** — When the REST API creates a session, it fires a background HTTP POST to the Game Engine and returns immediately. The bot starts as an `asyncio.create_task()` inside the Game Engine. This means the frontend gets a 201 response before the bot has even connected to the signaling server.

4. **Push-to-talk over VAD** — The user explicitly taps "Start Recording" / "Stop" rather than relying on Voice Activity Detection. When they tap "Stop", a `user_done` message flows through the signaling server to the bot, which triggers validation. VAD (SileroVAD) is still active as a fallback — if the user stops speaking for 4 seconds (Layer 3), or if enough transcript fragments accumulate (Layer 2), validation triggers automatically.

5. **TTSSpeakFrame vs TextFrame** — The bot uses `TTSSpeakFrame` (not `TextFrame`) because `TTSSpeakFrame` triggers proper audio context lifecycle in Pipecat's TTS pipeline. `TextFrame` was silently dropping audio because the TTS context was never marked as complete.

6. **British English voice** — TTS uses `aura-2-pandora-en` (British English) as the closest available voice to Indian English. Speed is set to 0.9 (10% slower than normal) for clarity.

7. **BFF proxy pattern** — The frontend never calls the REST API directly. All browser requests go to `/api/*` on the Next.js server, which proxies to `localhost:8000`. This keeps the backend URL and any future API keys server-side only.
