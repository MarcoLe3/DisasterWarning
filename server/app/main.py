from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CLIENT_ORIGIN
from app.routers import disasters
from app.telemetry import setup_telemetry

app = FastAPI(title="DisasterWarning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CLIENT_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(disasters.router)
setup_telemetry(app)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
