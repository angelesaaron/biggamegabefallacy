#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting BGGTDM Development Environment...${NC}\n"

# Function to cleanup background processes on exit
cleanup() {
    echo -e "\n${RED}Shutting down services...${NC}"
    kill $(jobs -p) 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

# Start Backend
echo -e "${GREEN}Starting Backend (FastAPI)...${NC}"
cd backend
source venv/bin/activate 2>/dev/null || {
    echo -e "${RED}Virtual environment not found. Please create it first:${NC}"
    echo "cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
}
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Start Frontend
echo -e "${GREEN}Starting Frontend (Next.js)...${NC}"
cd frontend
source ~/.nvm/nvm.sh 2>/dev/null
nvm use 18 2>/dev/null || echo -e "${RED}Warning: nvm not found or Node 18 not available${NC}"
npm run dev &
FRONTEND_PID=$!
cd ..

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Development servers started!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${BLUE}Backend:${NC}  http://localhost:8000"
echo -e "${BLUE}Frontend:${NC} http://localhost:3000 (or 3001 if 3000 is in use)"
echo -e "${GREEN}========================================${NC}"
echo -e "\nPress ${RED}Ctrl+C${NC} to stop all services\n"

# Wait for both processes
wait
