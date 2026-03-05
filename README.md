# BGGTDM (Big Game Gabe TD Model)

NFL touchdown prediction app that compares a proprietary ML model's TD probabilities against sportsbook odds. Surfaces value discrepancies, provides player-level insight, and presents everything in a clean, Sleeper-inspired UI.

## Core Concept

For any given NFL week, BGGTDM:
- Predicts the probability that a WR/TE will score a touchdown
- Converts that probability into implied American odds
- Compares against DraftKings and FanDuel anytime TD scorer odds
- Highlights where the model sees **value (edge)** relative to the market

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │────▶│  PostgreSQL  │
│   Next.js    │     │   FastAPI    │     │              │
│   Vercel     │     │   Render     │     │   Render     │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────▼───────┐
                     │  ML Model    │
                     │  (sklearn)   │
                     └──────────────┘
```

- **Frontend**: Next.js app with Tailwind CSS, deployed on Vercel
- **Backend**: FastAPI with 6 API routers (players, predictions, odds, game_logs, weeks, admin)
- **Database**: PostgreSQL (players, predictions, sportsbook_odds, game_logs, schedule, batch tracking)
- **ML Model**: scikit-learn Random Forest, generates TD probability per player per week
- **Data Source**: Tank01 NFL API for player data, game logs, schedules, and betting odds

## Local Development

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Set DATABASE_URL and TANK01_API_KEY in .env
uvicorn app.main:app --reload    # http://localhost:8000

# Frontend
cd frontend
npm install
npm run dev                       # http://localhost:3000
```

## Weekly Data Pipeline

Automated via GitHub Actions every Tuesday (after Monday Night Football):

```bash
cd backend
python scripts/update_weekly.py       # update schedule, game logs, odds (~556 API calls)
python scripts/generate_predictions.py # generate predictions (0 API calls)
```

See [`backend/scripts/README.md`](backend/scripts/README.md) for all available scripts.

## Project Structure

```
/
├── README.md
├── DEPLOYMENT_GUIDE.md
├── start-dev.sh
├── .github/workflows/weekly-update.yml
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers
│   │   ├── ml/             # Feature engineering, model service
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic response models
│   │   ├── services/       # Business logic services
│   │   ├── utils/          # Tank01 client, NFL calendar, odds conversion
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── models/             # ML model files (.pkl)
│   ├── scripts/            # Operational scripts
│   ├── sql/                # Reference SQL files
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── nfl_season_config.json
│   └── PREDICTION_ARCHITECTURE.md
└── frontend/
    ├── app/                # Next.js pages
    ├── components/         # React components
    ├── lib/                # Utilities
    ├── types/              # TypeScript interfaces
    └── public/             # Static assets
```

## Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for production deployment instructions (Render + Vercel).

## Disclaimer

BGGTDM is a personal analytics project. It is not financial advice, gambling advice, or a betting service. All data is provided for informational and educational purposes only.
