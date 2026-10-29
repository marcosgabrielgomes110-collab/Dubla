"""FastAPI application entry point.

Run with:
    uvicorn src.Dubla_Api.main:app --host 127.0.0.1 --port 8000
"""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.Dubla_Api import jobs, movies, settings, system
from src.Dubla_Config import ROOT

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
        protected = path.startswith("/api/v1") and path != "/api/v1/health"
        if token and protected:
            provided = request.headers.get("X-API-Token") or request.query_params.get("token")
            if provided != token:
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)

    app.include_router(system.router, prefix="/api/v1")
    app.include_router(settings.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(movies.router, prefix="/api/v1")

    @app.get("/")
    def root() -> dict:
        frontend = ROOT / "frontend" / "dist" / "index.html"
        if frontend.is_file():
            return FileResponse(frontend)
        return {
            "service": "dubla-api",
            "version": VERSION,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    # Serve the built SPA when frontend/dist exists (production mode)
    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
                return JSONResponse({"detail": "not found"}, status_code=404)
            candidate = (dist / full_path).resolve()
            try:
                candidate.relative_to(dist.resolve())
            except ValueError:
                return JSONResponse({"detail": "not found"}, status_code=404)
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
