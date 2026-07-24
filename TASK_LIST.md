# The Memory Host — Task List

> Based on the [Implementation Roadmap](./ARCHITECTURE.md#16-implementation-roadmap)

---

## Phase 1 — Foundation (Steps 1–4)

- [ ] **Step 1: Project scaffold** — Python venv, FastAPI, config, Docker
  - `backend/pyproject.toml` / `requirements.txt`
  - `backend/config.py` — environment config
  - `docker-compose.yml` — PostgreSQL + backend
- [ ] **Step 2: Word pool + game logic** — 100+ words, sequence generation, validation
  - `backend/word_pool.py`
  - `backend/game_logic.py`
- [ ] **Step 3: Game state machine** — enum, dataclass, transitions
  - `backend/game_state.py`
- [ ] **Step 4: Database models + migrations** — SQLAlchemy + Alembic
  - `backend/models/` (base, session, round)
  - `backend/db/` (connection, migrations)

---

## Phase 2 — Backend APIs (Steps 5–6)

- [ ] **Step 5: FastAPI routes** — session CRUD, leaderboard, SmallWebRTC room creation
  - `backend/api/` (main, routes, models/pydantic, deps)
- [ ] **Step 6: Cache layer** — in-memory TTLCache
  - `backend/cache.py`

---

## Phase 3 — Voice Pipeline (Steps 7–10)

- [ ] **Step 7: Prompt templates** — categorized dialog templates with random selection
  - `backend/prompt_templates.py`
- [ ] **Step 8: MemoryGameProcessor** — custom Pipecat FrameProcessor
  - `backend/game_processor.py`
- [ ] **Step 9: Pipecat pipeline assembly** — SmallWebRTC transport + STT + TTS + processor
  - `backend/bot.py`
- [ ] **Step 10: Interruption handling** — graceful recovery when user interrupts bot
  - (within `backend/game_processor.py`)

---

## Phase 4 — Frontend (Steps 11–14)

- [ ] **Step 11: Next.js scaffold** — pages, layout, API routes (BFF), styling
  - `frontend/` scaffold (package.json, tsconfig, next.config, etc.)
  - `frontend/app/` pages (landing, game/[sessionId], leaderboard)
  - `frontend/app/api/` BFF routes
- [ ] **Step 12: SmallWebRTC integration** — WebRTC client, room join, SSR-safe dynamic import
  - `frontend/components/WebRTCRoom.tsx`
- [ ] **Step 13: Game state display** — polling hook, header, game log, game over modal
  - `frontend/hooks/useGameState.ts`
  - `frontend/components/GameHeader.tsx`
  - `frontend/components/GameLog.tsx`
  - `frontend/components/GameOverModal.tsx`
- [ ] **Step 14: Leaderboard page** — fetch from API, display table
  - `frontend/app/leaderboard/page.tsx`
  - `frontend/hooks/useLeaderboard.ts`
  - `frontend/components/LeaderboardTable.tsx`

---

## Phase 5 — Polish & Testing (Steps 15–17)

- [ ] **Step 15: Double-scoring prevention** — DB constraints + application checks
  - `backend/game_processor.py` (validation guard)
  - DB migration (UNIQUE constraint)
- [ ] **Step 16: Unit tests** — game logic, API, processor, prompt templates
  - `backend/tests/` (test_game_logic, test_api, test_prompt_templates, test_processor)
- [ ] **Step 17: README + setup instructions** — environment, running instructions
  - `README.md`

---

## Quick Reference

| Phase | Steps | Description | Est. Time |
|-------|-------|-------------|-----------|
| 1 | 1–4 | Foundation (scaffold, logic, state, DB) | ~4 hr |
| 2 | 5–6 | Backend APIs (routes, cache) | ~2.5 hr |
| 3 | 7–10 | Voice Pipeline (templates, processor, bot, interruptions) | ~7 hr |
| 4 | 11–14 | Frontend (Next.js, WebRTC, game UI, leaderboard) | ~4.5 hr |
| 5 | 15–17 | Polish & Testing (double-scoring, tests, README) | ~3.5 hr |
| **Total** | **1–17** | **All steps** | **~18 hr** |
