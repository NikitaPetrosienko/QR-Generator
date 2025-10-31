from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.qr import router as qr_router

# NEW: metrics
from backend.app.metrics import metrics_middleware, router as metrics_router

app = FastAPI(title="QR Generator Service", version="2.0.0")

app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "HEAD"],
    allow_headers=["*"],
)

# NEW: attach metrics middleware
app.middleware("http")(metrics_middleware)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# NEW: expose /metrics.txt (secured)
app.include_router(metrics_router)

app.include_router(qr_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
