# Data Migration Scripts

## Overview

These scripts help you migrate your existing CSV data into the PostgreSQL database.

## Prerequisites

1. PostgreSQL database running and accessible
2. Database URL configured in `.env` file
3. Python virtual environment activated with all dependencies installed

## Running the Migration

### Step 1: Set up environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configure database

Copy `.env.example` to `.env` and update the `DATABASE_URL`:

```bash
cp .env.example .env
# Edit .env with your database credentials
```

Example DATABASE_URL:
```
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/bggtdm
```

### Step 3: Run migration

```bash
python migrations/migrate_csv_data.py
```

This will:
- Create all database tables
- Migrate players from roster CSV files
- Migrate model predictions from modelOdds CSV files
- Migrate sportsbook odds from sportsbookOdds CSV files
- Migrate value picks from historicalOdds CSV files
- Migrate game results from roster_game_logs.csv

## What Gets Migrated

### Players
- Source: `data/rosters/*.csv`
- Target: `players` table
- Includes: player info, team, position, stats, headshot URL

### Model Predictions
- Source: `data/modelOdds/*.csv`
- Target: `predictions` table
- Includes: TD likelihood, model odds, favor

### Sportsbook Odds
- Source: `data/sportsbookOdds/*.csv`
- Target: `sportsbook_odds` table
- Includes: odds from DraftKings, FanDuel, BetMGM, etc.

### Value Picks
- Source: `data/historicalOdds/[sportsbook]/*.csv`
- Target: `value_picks` table
- Includes: weighted value calculations

### Game Results
- Source: `data/roster_game_logs.csv`
- Target: `game_results` table
- Includes: actual TDs, receptions, yards, targets

## Troubleshooting

### "No module named 'app'"

Make sure you're running from the `backend/` directory:

```bash
cd backend
python migrations/migrate_csv_data.py
```

### Database connection errors

Check your DATABASE_URL in `.env` file and ensure PostgreSQL is running.

### Duplicate key errors

The migration script checks for existing records and skips duplicates. If you want to re-run the migration, you can either:
1. Drop and recreate the database
2. Manually delete specific records

## Next Steps

After migration, you can:
1. Start the FastAPI server: `uvicorn app.main:app --reload`
2. Visit the API docs at `http://localhost:8000/docs`
3. Test API endpoints
4. Start the frontend development server
