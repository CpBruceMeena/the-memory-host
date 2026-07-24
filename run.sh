#!/usr/bin/env bash
#
# run.sh — Start The Memory Host (rest-api + game-engine + frontend)
#
# Usage:
#   ./run.sh                  # Start both: rest-api + game-engine + frontend
#   ./run.sh rest-api         # Start REST API server (port 8000)
#   ./run.sh game-engine      # Start game engine (signaling 3001 + HTTP 3002)
#   ./run.sh frontend         # Start frontend only (port 3000)
#   ./run.sh db               # PostgreSQL status (already running)
#
# Prerequisites:
#   - PostgreSQL running (via Docker or native)
#   - Python venv activated with dependencies installed
#   - Node.js dependencies installed in frontend/
#   - .env file configured (copy from .env.example)
#
# Architecture:
#   rest-api/       Port 8000  — Session CRUD, leaderboard, health
#   game-engine/    Port 3002  — Voice bot, game processor (signaling on 3001)
#   frontend/       Port 3000  — Next.js UI
#

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
REST_API_DIR="$ROOT_DIR/backend/rest-api"
GAME_ENGINE_DIR="$ROOT_DIR/backend/game-engine"
FRONTEND_DIR="$ROOT_DIR/frontend"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERR]${NC}  $1"; }

# ── Health checks ───────────────────────────────────────────

check_deps() {
    local SERVICE_DIR="$1"
    local SERVICE_NAME="$2"

    if [ ! -f "$SERVICE_DIR/.venv/bin/python" ]; then
        warn "Python venv not found at $SERVICE_DIR/.venv/"
        info "Create it: cd $SERVICE_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
        return 1
    fi

    # Check Node modules (only for rest-api check, since frontend needs it)
    if [ ! -d "$FRONTEND_DIR/node_modules" ] && [ "$SERVICE_NAME" != "game-engine" ]; then
        warn "Node modules not found in frontend/"
        info "Install them: cd $FRONTEND_DIR && npm install"
        return 1
    fi

    return 0
}

# ── Start services ──────────────────────────────────────────

start_rest_api() {
    info "Starting REST API server on port 8000..."

    cd "$REST_API_DIR"
    source .venv/bin/activate

    # Create database tables on startup
    info "Ensuring database tables exist..."
    python -c "
import asyncio
from app.db.database import create_tables
asyncio.run(create_tables())
print('Tables ready')
    " 2>&1 | grep -v "UserWarning" || warn "Could not create tables (db might not be ready)"

    # Start FastAPI server
    uvicorn app.api.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --log-level info
}

start_game_engine() {
    info "Starting Game Engine on port 3002 (signaling on port 3001)..."

    cd "$GAME_ENGINE_DIR"
    source .venv/bin/activate

    # Start FastAPI server (includes signaling server via lifespan)
    uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 3002 \
        --reload \
        --log-level info
}

start_frontend() {
    info "Starting frontend (Next.js) on port 3000..."
    cd "$FRONTEND_DIR"
    npm run dev
}

# ── Main ────────────────────────────────────────────────────

print_banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           The Memory Host                   ║${NC}"
    echo -e "${CYAN}║      Voice-Based Memory Card Game           ║${NC}"
    echo -e "${CYAN}║                                            ║${NC}"
    echo -e "${CYAN}║  rest-api/    Port 8000  — API endpoints    ║${NC}"
    echo -e "${CYAN}║  game-engine/ Port 3002  — Voice bot        ║${NC}"
    echo -e "${CYAN}║  frontend/    Port 3000  — Next.js UI       ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
}

print_banner

case "${1:-all}" in
    db)
        info "PostgreSQL should be running on localhost:5432"
        info "(The application connects automatically via DATABASE_URL)"
        ;;
    rest-api)
        check_deps "$REST_API_DIR" "rest-api" || exit 1
        start_rest_api
        ;;
    game-engine)
        check_deps "$GAME_ENGINE_DIR" "game-engine" || exit 1
        start_game_engine
        ;;
    frontend)
        check_deps "$FRONTEND_DIR" "frontend" || exit 1
        start_frontend
        ;;
    all)
        check_deps "$REST_API_DIR" "rest-api" || exit 1
        check_deps "$GAME_ENGINE_DIR" "game-engine" || exit 1

        # Kill any lingering processes on our ports
        for port in 8000 3002 3001; do
            lsof -ti :$port 2>/dev/null | xargs kill -9 2>/dev/null || true
        done

        # Start REST API in background
        info "Starting REST API in background..."
        cd "$REST_API_DIR"
        source .venv/bin/activate
        uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload &
        REST_API_PID=$!
        cd "$ROOT_DIR"

        # Start Game Engine in background
        info "Starting Game Engine in background..."
        cd "$GAME_ENGINE_DIR"
        source .venv/bin/activate
        uvicorn app.main:app --host 0.0.0.0 --port 3002 --reload &
        GAME_ENGINE_PID=$!
        cd "$ROOT_DIR"

        # Wait a moment for services to start
        sleep 2

        # Start frontend in foreground
        start_frontend

        # Cleanup on exit
        info "Shutting down..."
        kill "$REST_API_PID" "$GAME_ENGINE_PID" 2>/dev/null || true
        ok "Done!"
        ;;
    *)
        echo "Usage: $0 {rest-api|game-engine|frontend|db|all}"
        exit 1
        ;;
esac
