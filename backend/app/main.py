# backend/app/main.py
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.qr import router as qr_router

# === metrics & logging (твои новые файлы) ===
from backend.app.logs.metrics_basic import metrics_middleware
from backend.app.logs.logging_conf import setup_logging

# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(title="QR Generator Service", version="2.0.0")

# --- ensure log dir exists (для файлового хендлера) ---
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- configure logging: в stdout + в logs/qr_service.log ---
setup_logging(to_stdout=True, file_path=str(LOG_DIR / "qr_service.log"))

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "HEAD"],
    allow_headers=["*"],
)

# --- статический фронт (/ui) ---
app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")

# --- метрики (тайминги + статус) ---
app.middleware("http")(metrics_middleware)

# --- health ---
@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# --- QR endpoints ---
app.include_router(qr_router)

# --- uvicorn dev-run ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
