"""FastAPI application entrypoint for GERAT Web."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, classrooms, hydro, projects, simulation, thermal
from app.core.config import get_settings
from app.db.seed import run_seed
from app.db.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run idempotent seed on startup."""
    try:
        async with AsyncSessionLocal() as session:
            await run_seed(session)
    except Exception as exc:  # pragma: no cover
        logger.warning("Seed inicial não pôde ser executado no startup: %s", exc)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = settings.API_V1_PREFIX

    @app.get(f"{prefix}/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "gerat-backend"}

    app.include_router(auth.router, prefix=prefix)
    app.include_router(classrooms.router, prefix=prefix)
    app.include_router(projects.router, prefix=prefix)
    app.include_router(hydro.router, prefix=prefix)
    app.include_router(thermal.router, prefix=prefix)
    app.include_router(simulation.router, prefix=prefix)

    return app


app = create_app()
