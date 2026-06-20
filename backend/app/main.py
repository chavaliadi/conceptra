from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.plans import router as plans_router
from app.api.routes.plans_v2 import router as plans_v2_router
from app.api.routes.ai_routes import router as ai_router
from app.database import close_db
from app.services.cache_service import init_redis, close_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield
    await close_db()
    await close_redis()


app = FastAPI(title="Conceptra API", version="0.1.0", lifespan=lifespan)

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



@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

