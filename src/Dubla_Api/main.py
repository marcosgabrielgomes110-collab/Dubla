"""FastAPI application entry point.

Run with:
    uvicorn src.Dubla_Api.main:app --host 127.0.0.1 --port 8000
"""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.Dubla_Api import jobs, movies, settings, system

VERSION = "1.0.0"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Dubla API",
        version=VERSION,
        description="HTTP API for the Dubla dubbing pipeline (download, STT, translation, voice, mux).",
    )

    origins = [
        item.strip()
        for item in os.getenv(
            "DUBLA_CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        ).split(",")
        if item.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Range", "Accept-Ranges"],
    )

    @app.middleware("http")
    async def auth(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        token = os.getenv("DUBLA_API_TOKEN")
        path = request.url.path
        public = (
            path in ("/", "/api/v1/health", "/health")
            or path.startswith(("/docs", "/redoc", "/openapi.json"))
        )
        if token and not public:
            if request.headers.get("X-API-Token") != token:
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)

    app.include_router(system.router, prefix="/api/v1")
    app.include_router(settings.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(movies.router, prefix="/api/v1")

    @app.get("/")
    def root() -> dict:
        return {
            "service": "dubla-api",
            "version": VERSION,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()
