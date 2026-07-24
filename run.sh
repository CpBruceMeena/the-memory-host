#!/usr/bin/env bash
#
# run.sh — Start The Memory Host (backend + frontend)
#
# Usage:
#   ./run.sh              # Start both
#   ./run.sh backend      # Start backend only
#   ./run.sh frontend     # Start frontend only
#   ./run.sh db           # Start PostgreSQL only
#
# Prerequisites:
#   - PostgreSQL running (via Docker or native)
#   - Python venv activated with dependencies installed
#   - Node.js dependencies installed in frontend/
#   - .env file configured (copy from .env.example)
#

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
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
    # Check Python venv
    if [ ! -f "$BACKEND_DIR/.venv/bin/python" ]; then
        warn "Python venv not found at backend/.venv/"
        info "Create it: cd $BACKEND_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
        return 1
    fi

    # Check Node modules
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        warn "Node modules not found in frontend/"
        info "Install them: cd $FRONTEND_DIR && npm install"
        return 1
    fi

    # Check .env file
    if [ ! -f "$ROOT_DIR/.env" ]; then
        warn ".env file not found at project root"
        info "Create it: cp .env.example .env"
        return 1
    fi

    return 0
}

start_db() {
    info "Starting PostgreSQL via Docker Compose..."
    cd "$ROOT_DIR"
    docker compose up -d postgres
    info "Waiting for PostgreSQL to be healthy..."
    sleep 3
    ok "PostgreSQL is running on port 5432"
}

start_backend() {
    info "Starting backend (FastAPI) on port 8000..."

    # Activate venv and run uvicorn
    cd "$BACKEND_DIR"
    source .venv/bin/activate

    # Create database tables on startup
    info "Creating database tables..."
    python -c "
import asyncio
from app.db.database import create_tables
asyncio.run(create_tables())
print('Tables created successfully')
    " || warn "Could not create tables (db might not be ready)"

    # Start FastAPI server
    uvicorn app.api.main:app \
        --host 0.0.0.0 \
        --port 8000 \
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
    echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║        The Memory Host              ║${NC}"
    echo -e "${CYAN}║   Voice-Based Memory Card Game      ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
    echo ""
}

print_banner

case "${1:-all}" in
    db)
        start_db
        ;;
    backend)
        check_deps || exit 1
        start_backend
        ;;
    frontend)
        check_deps || exit 1
        start_frontend
        ;;
    all)
        check_deps || exit 1
        # Start PostgreSQL in background
        start_db

        # Start backend in background
        info "Starting backend in background..."
        cd "$BACKEND_DIR"
        source .venv/bin/activate
        uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload &
        BACKEND_PID=$!
        cd "$ROOT_DIR"

        # Start frontend in foreground
        start_frontend

        # Cleanup on exit
        info "Shutting down..."
        kill "$BACKEND_PID" 2>/dev/null || true
        ok "Done!"
        ;;
    *)
        echo "Usage: $0 {backend|frontend|db|all}"
        exit 1
        ;;
esac
