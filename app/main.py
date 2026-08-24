from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.services import ml_service

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "frontend" / "dist"

load_dotenv(ROOT / ".env")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Warm the model so the first demo click is fast.
    try:
        if ml_service.MODEL_PATH.exists():
            ml_service.load_model()
    except Exception:
        # Health endpoint will report the failure; don't block startup.
        pass
    yield


app = FastAPI(
    title="Chargeback Sentinel",
    description=(
        "Defense-only representment desk: ML predicts winnability; "
        "LLM assembles evidence only for RECOMMEND_CONTEST cases."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.exception_handler(FileNotFoundError)
async def missing_artifact(_: Request, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": f"Unexpected server error: {exc.__class__.__name__}"},
    )


def _ui_ready() -> bool:
    return (STATIC_DIR / "index.html").exists()


@app.get("/api")
def api_root() -> dict:
    return {
        "service": "chargeback-sentinel",
        "docs": "/docs",
        "health": "/api/health",
        "ui": "/" if _ui_ready() else None,
    }


if _ui_ready():
    # Mount last so /api and /docs keep precedence.
    app.mount(
        "/",
        StaticFiles(directory=STATIC_DIR, html=True),
        name="ui",
    )
else:

    @app.get("/")
    def root() -> dict:
        return {
            "service": "chargeback-sentinel",
            "docs": "/docs",
            "health": "/api/health",
            "ui_hint": (
                "Build the UI with: cd frontend && npm ci && npm run build "
                "(or use the production Dockerfile)."
            ),
        }
