"""
NFT Inspector FastAPI server.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .config import settings
from .database import database_manager
from .routes import analysis, leaderboard, health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown."""
    await database_manager.initialize()
    logger.info("Database connected")
    yield
    await database_manager.close()


app = FastAPI(
    title="NFT Inspector API",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    lifespan=lifespan
)

# CORS for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)



app.include_router(health.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(leaderboard.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"name": "NFT Inspector API", "health": "/api/v1/health"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)