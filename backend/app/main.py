# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.qr import router as qr_router

app = FastAPI(title="QR Generator Service", version="2.0.0")

# Отдаём UI из папки frontend (как и было)
app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")

# CORS: добавили POST/OPTIONS для загрузки логотипа через multipart/form-data
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # при необходимости сузить до домена портала
    allow_credentials=True,
    allow_methods=["GET", "HEAD", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# API роуты
app.include_router(qr_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
