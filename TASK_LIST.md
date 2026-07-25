# The Memory Host — Task List

> Based on the [Implementation Roadmap](./ARCHITECTURE.md#17-implementation-roadmap)

---

## Phase 1 — Foundation (Steps 1–4)

- [x] **Step 1: Project scaffold** — Python venv, FastAPI, config
  - `backend/requirements.txt` ✅
  - `backend/app/core/config.py` (was `backend/config.py`) ✅
  - `run.sh` — start backend / frontend ✅

- [x] **Step 2: Word pool + game logic** — 100+ words, sequence generation, validation
  - `backend/app/core/constants.py` (moved from `backend/word_pool.py`) ✅
  - `backend/app/services/game_logic.py` (was `backend/game_logic.py`) ✅

- [x] **Step 3: Game state machine** — enum, dataclass, transitions
  - `backend/app/services/game_state.py` (was `backend/game_state.py`) ✅

- [x] **Step 4: Database models + migrations** — SQLAlchemy
  - `backend/app/models/` (base, session, round) ✅
  - `backend/app/db/database.py` (connection + create_tables) ✅
  - Alembic not set up — using `create_tables()` for dev

---

## Phase 2 — Backend APIs (Steps 5–6)

- [x] **Step 5: FastAPI routes** — session CRUD, leaderboard, health
  - `backend/app/api/main.py` ✅
  - `backend/app/api/routes.py` ✅
  - `backend/app/api/schemas.py` (Pydantic models) ✅
  - `backend/app/api/deps.py` (DI: DB + cache) ✅

- [x] **Step 6: Cache layer** — in-memory TTLCache
  - `backend/app/core/cache.py` (was `backend/cache.py`) ✅

---

## Phase 3 — Voice Pipeline (Steps 7–10)

- [x] **Step 7: Prompt templates** — categorized dialog templates with random selection
  - `backend/app/services/prompt_templates.py` ✅
  - 26 templates across 7 categories: start, round_intro, success, failure, game_over, interrupt, waiting

- [x] **Step 8: MemoryGameProcessor** — custom Pipecat FrameProcessor
  - `backend/app/services/game_processor.py` ✅
  - Full state machine, validation, DB persistence, double-scoring prevention

- [x] **Step 9: Pipecat pipeline assembly** — SmallWebRTC transport + STT + TTS + processor
  - `backend/app/services/bot.py` ✅
  - Uses Pipecat's built-in `SmallWebRTCTransport` (not a placeholder)
  - WebSocket `SignalingClient` for SDP exchange

- [x] **Step 10: Interruption handling** — graceful recovery when user interrupts bot
  - Integrated in `backend/app/services/game_processor.py` ✅
  - SPEAK_SEQUENCE → LISTEN on user interrupt

---

## Phase 4 — Frontend (Steps 11–14)

- [x] **Step 11: Next.js scaffold** — pages, layout, API routes (BFF), styling
  - `frontend/` scaffold (package.json, tsconfig, next.config, tailwind) ✅
  - `frontend/app/layout.tsx` — root layout + nav ✅
  - `frontend/app/page.tsx` — landing page (hero, name form, features) ✅
  - `frontend/app/loading.tsx` — loading state ✅
  - `frontend/app/game/[sessionId]/page.tsx` — game room ✅
  - `frontend/app/leaderboard/page.tsx` — leaderboard page ✅
  - `frontend/app/api/sessions/route.ts` — BFF: create session ✅
  - `frontend/app/api/sessions/[id]/route.ts` — BFF: get session ✅
  - `frontend/app/api/sessions/[id]/end/route.ts` — BFF: end session ✅
  - `frontend/app/api/leaderboard/route.ts` — BFF: leaderboard ✅

- [x] **Step 12: SmallWebRTC integration** — WebRTC client, room join, SSR-safe dynamic import
  - `frontend/components/WebRTCRoom.tsx` — full WebRTC with WebSocket signaling ✅

- [x] **Step 13: Game state display** — polling hook, header, game log, game over modal
  - `frontend/hooks/useGameState.ts` — 2s polling ✅
  - `frontend/components/GameHeader.tsx` — score, round, progress bar ✅
  - `frontend/components/GameLog.tsx` — round history ✅
  - `frontend/components/GameOverModal.tsx` — final stats + replay ✅
  - `frontend/components/PlayerNameForm.tsx` — validated input ✅
  - `frontend/components/LoadingSkeleton.tsx` — card/text/page variants ✅

- [x] **Step 14: Leaderboard page** — fetch from API, display table
  - `frontend/app/leaderboard/page.tsx` ✅
  - `frontend/hooks/useLeaderboard.ts` — fetch + 30s auto-refresh ✅
  - `frontend/components/LeaderboardTable.tsx` — ranked table with medals ✅

---

## Quick Reference

| Phase | Steps | Description | Est. Time | Status |
|-------|-------|-------------|-----------|--------|
| 1 | 1–4 | Foundation (scaffold, logic, state, DB) | ~4 hr | ✅ Complete |
| 2 | 5–6 | Backend APIs (routes, cache) | ~2.5 hr | ✅ Complete |
| 3 | 7–10 | Voice Pipeline (templates, processor, bot, interruptions) | ~7 hr | ✅ Complete |
| 4 | 11–14 | Frontend (Next.js, WebRTC, game UI, leaderboard) | ~4.5 hr | ✅ Complete |
| **Total** | **1–14** | **All steps** | **~18 hr** | **🎉 All complete** |

---

## Summary

All 14 steps completed across 4 phases. The full integration test (backend health, API, frontend compilation) has been verified working.

Additional completed items:
- **Double-scoring prevention** — 3-layer protection (in-memory guard, DB constraint, app-level check)
- **README** — full setup, architecture, API docs
