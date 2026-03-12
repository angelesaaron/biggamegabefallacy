#!/bin/bash
# dev.sh — start backend + frontend for local development

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend_new"
FRONTEND="$ROOT/frontend"

# Cleanup background processes on exit
trap 'echo "\nShutting down..."; kill $(jobs -p) 2>/dev/null' EXIT INT TERM

echo "Starting backend on :8000..."
(
  cd "$BACKEND"
  source .venv/bin/activate
  uvicorn app.main:app --reload --port 8000
) &

echo "Starting frontend on :3000..."
(
  cd "$FRONTEND"
  npm run dev
) &

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both."

wait
