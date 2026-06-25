import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes.plans import router as plans_router
from app.api.routes.plans_v2 import router as plans_v2_router
from app.api.routes.ai_routes import router as ai_router
from app.api.routes.social_routes import router as social_router
from app.api.routes.tutor_routes import router as tutor_router
from app.database import close_db
from app.limiter import limiter
from app.services.cache_service import init_redis, close_redis

# ─── SENTRY INSTRUMENTATION ──────────────────────────────────────────────────
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastAPIIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[FastAPIIntegration()],
            traces_sample_rate=1.0,
        )
        print("Sentry initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize Sentry: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield
    await close_db()
    await close_redis()


app = FastAPI(title="Conceptra API", version="0.1.0", lifespan=lifespan)

# ─── RATE LIMITER REGISTER ──────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plans_router)
app.include_router(plans_v2_router)
app.include_router(ai_router)
app.include_router(social_router)
app.include_router(tutor_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ─── PROMETHEUS METRICS ENDPOINT ──────────────────────────────────────────────

@app.get("/metrics")
def metrics():
    """Prometheus exporter scraper target."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
