from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.plans import router as plans_router

app = FastAPI(title="Conceptra API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plans_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
