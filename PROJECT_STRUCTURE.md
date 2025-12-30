# Big Game Gabe TD Fallacy - Project Structure

## Overview

This project consists of a FastAPI backend for NFL touchdown predictions and a Next.js frontend for visualization.

## Directory Structure

```
biggamegabefallacy/
├── backend/                    # FastAPI backend application
│   ├── app/                    # Main application code
│   │   ├── api/               # API route handlers
│   │   │   ├── game_logs.py
│   │   │   ├── odds.py
│   │   │   ├── players.py
│   │   │   ├── predictions.py
│   │   │   └── schedule.py
│   │   ├── ml/                # Machine learning components
│   │   │   ├── feature_engineering.py
│   │   │   └── model_service.py
│   │   ├── models/            # SQLAlchemy database models
│   │   │   ├── game_log.py
│   │   │   ├── odds.py
│   │   │   ├── player.py
│   │   │   ├── prediction.py
│   │   │   └── schedule.py
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic services
│   │   │   ├── data_service.py
│   │   │   ├── prediction_service.py  # UNIFIED PREDICTION SERVICE
│   │   │   └── tank01_service.py
│   │   ├── utils/             # Utility functions
│   │   ├── config.py          # Configuration settings
│   │   ├── database.py        # Database connection
│   │   └── main.py           # FastAPI application entry point
│   ├── migrations/            # Alembic database migrations
│   ├── venv/                  # Python virtual environment
│   ├── .env                   # Environment variables (not in git)
│   ├── .env.example          # Example environment variables
│   ├── requirements.txt       # Python dependencies
│   │
│   # Data Sync Scripts
│   ├── sync_rosters.py        # Sync player rosters from Tank01
│   ├── sync_game_logs.py      # Sync game logs from Tank01
│   ├── sync_schedule.py       # Sync NFL schedule from Tank01
│   ├── sync_odds.py           # Sync sportsbook odds
│   │
│   # Prediction Scripts
│   ├── generate_historical_predictions.py  # Generate historical predictions (run once)
│   ├── generate_predictions.py            # Generate current week predictions
│   ├── update_weekly.py                   # Full weekly update workflow
│   │
│   # Database Scripts
│   ├── create_tables.py       # Create database tables
│   ├── setup_database.sh      # Database setup script
│   ├── add_jersey_number_column.py  # Migration script
│   │
│   # Backfill Scripts
│   ├── backfill_historical_odds.py  # Backfill historical odds data
│   │
│   # Documentation
│   ├── PREDICTION_ARCHITECTURE.md    # Unified prediction service architecture
│   ├── SCRIPTS_REFERENCE.md          # Reference for all backend scripts
│   ├── END_TO_END_GUIDE.md          # Complete workflow guide
│   ├── DATA_SYNC_GUIDE.md           # Data synchronization guide
│   ├── ODDS_INTEGRATION.md          # Odds integration documentation
│   ├── WORKFLOW.md                  # Weekly workflow documentation
│   ├── DATA_FLOW_CLARIFICATION.md   # Data flow clarification
│   └── BACKEND_COMPLETE_STATUS.md   # Backend completion status
│
├── frontend/                   # Next.js frontend application
│   ├── app/                    # Next.js app router
│   │   ├── about/             # About page
│   │   ├── performance/       # Performance page
│   │   ├── players/           # Players page (Player Model tab)
│   │   ├── value-finder/      # Value Finder page (Weekly Value tab)
│   │   ├── globals.css        # Global styles (Tailwind v4)
│   │   ├── layout.tsx         # Root layout
│   │   └── page.tsx           # Home page
│   ├── components/            # React components
│   │   ├── GameLogTable.tsx         # Game log table component
│   │   ├── GamblingDisclaimer.tsx   # Gambling disclaimer
│   │   ├── PlayerHeader.tsx         # Player header component
│   │   ├── PlayerModel.tsx          # Main player model component
│   │   ├── PlayerSelector.tsx       # Player dropdown selector
│   │   ├── PredictionSummary.tsx    # Prediction summary component
│   │   ├── ProbabilityChart.tsx     # Weekly probability chart
│   │   ├── ValuePlayerCard.tsx      # Value player card component
│   │   └── WeeklyValue.tsx          # Weekly value tab component
│   ├── public/                # Static assets
│   │   └── gabe-davis-background.jpg
│   ├── node_modules/          # Node.js dependencies
│   ├── package.json           # Node.js dependencies config
│   └── next.config.ts         # Next.js configuration
│
├── data/                       # Data files (CSV exports, etc.)
├── models/                     # Trained ML models (.pkl files)
├── jsondummyresponses/        # JSON response examples for testing
│
└── PROJECT_STRUCTURE.md       # This file
```

## Key Architecture Decisions

### Unified Prediction Service
All prediction generation flows through a single source of truth:
- **Service**: `backend/app/services/prediction_service.py`
- **API Endpoint**: `/api/predictions/generate/{player_id}` uses this service
- **Batch Script**: `generate_historical_predictions.py` uses this service
- **Documentation**: See `backend/PREDICTION_ARCHITECTURE.md`

### Backend Structure
- **FastAPI** with async SQLAlchemy for database operations
- **PostgreSQL** database for all data storage
- **Tank01 NFL API** for player rosters, game logs, and schedules
- **Odds API** for sportsbook odds data
- **Random Forest ML model** for touchdown probability prediction

### Frontend Structure
- **Next.js 14** with App Router
- **Tailwind CSS v4** for styling
- **Two main tabs**:
  - Player Model: Individual player predictions and analysis
  - Weekly Value: Week-by-week value plays across all players

## Removed Legacy Files (Cleanup 2025-12-29)

The following legacy files have been removed:
- `.streamlit/` - Old Streamlit app configuration
- `streamlit-app.py` - Legacy Streamlit application
- `oldcode/` - Old code directory
- `model_creation_old/` - Old model creation scripts
- `figma-make/` - Figma design files (no longer needed)
- `images/` - Old images directory (background moved to frontend/public/)
- `test_*.py` - Backend test files (5 files)
- `RUN_TESTS.md` - Test documentation (tests removed)
- `run_all_tests.sh` - Test runner script (tests removed)
- `utils.py` - Old Streamlit utility functions

## Development Workflow

### Backend Development
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Frontend Development
```bash
cd frontend
npm run dev
```

### Weekly Data Update
```bash
cd backend
source venv/bin/activate
python update_weekly.py  # Syncs all data and generates predictions
```

## Environment Variables

See `backend/.env.example` for required environment variables:
- `DATABASE_URL` - PostgreSQL connection string
- `TANK01_API_KEY` - Tank01 NFL API key
- `ODDS_API_KEY` - Odds API key
- `MODEL_PATH` - Path to trained ML model
