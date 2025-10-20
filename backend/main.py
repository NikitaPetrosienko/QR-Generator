from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.vcard_portal import router as vcard_router

app = FastAPI(
    title="QR vCard API",
    version="2.0.0",
)

# CORS:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    """Проверка живости (для Docker healthcheck)."""
    return {"status": "ok"}

app.include_router(vcard_router, prefix="")
