import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import settings
from app.limiter import limiter
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.public import router as public_router
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are managed by Alembic — not auto-created here.
    from app.ml.model_bundle import load_bundle
    try:
        load_bundle()
        logger.info("Model bundle loaded at startup")
    except FileNotFoundError as exc:
        logger.warning("Model bundle not found at startup: %s", exc)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Attach limiter state and its 429 exception handler.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Middleware — CORS first (outermost layer in Starlette's LIFO stack).
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Key"],
)


# Security headers middleware runs after CORS (added last = runs first in
# Starlette's LIFO execution order, i.e. wraps every response).
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # CSP: allow self + same-origin API calls; no inline scripts
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; connect-src 'self'"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )
    return response


# ---------------------------------------------------------------------------
# Routers — auth first so login/token routes resolve before public/admin.
# ---------------------------------------------------------------------------
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(public_router, prefix="/api")


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


# ---------------------------------------------------------------------------
# Health endpoint — rate-limited to prevent abuse of DB probe.
# ---------------------------------------------------------------------------
@app.get("/health")
@limiter.limit("30/minute")
async def health(request: Request) -> dict:
    from app.ml.model_bundle import _bundle_cache

    db_ok = False
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Health check DB probe failed")

    model_loaded = _bundle_cache is not None
    all_ok = db_ok and model_loaded

    return {
        "status": "ok" if all_ok else "degraded",
        "version": "2.0.0",
        "db": "ok" if db_ok else "unavailable",
        "model_loaded": model_loaded,
    }
