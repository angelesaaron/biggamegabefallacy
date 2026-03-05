from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.api import players, predictions, odds, admin, game_logs, weeks

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="BGGTDM API",
    description="Big Game Gabe TD Model - NFL Touchdown Prediction API",
    version="1.0.0",
    lifespan=lifespan
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(players.router, prefix="/api/players", tags=["Players"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["Predictions"])
app.include_router(odds.router, prefix="/api/odds", tags=["Odds"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(game_logs.router, prefix="/api/game-logs", tags=["Game Logs"])
app.include_router(weeks.router)


@app.get("/")
async def root():
    return {
        "message": "BGGTDM API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
