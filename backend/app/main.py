from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# импортируем роуты
from backend.app.api import qr_url, qr_phone, qr_mail, qr_sms, qr_vcard


# ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ

app = FastAPI(
    title="QR Generator Service",
    version="2.0.0",
    description="Сервис генерации QR-кодов (URL, Phone, Mail, SMS, vCard)",
)

# CORS (для портала)
# В закрытом контуре можно оставить ["*"], иначе указать домены портала
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Раздача фронта
app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")

# Healthcheck (для Docker)
@app.get("/healthz")
def healthz():
    """Проверка живости контейнера (Docker HEALTHCHECK)."""
    return {"status": "ok"}

# Подключение роутов
app.include_router(qr_url.router, prefix="/qr", tags=["URL"])
app.include_router(qr_phone.router, prefix="/qr", tags=["Phone"])
app.include_router(qr_mail.router, prefix="/qr", tags=["Mail"])
app.include_router(qr_sms.router, prefix="/qr", tags=["SMS"])
app.include_router(qr_vcard.router, prefix="/qr", tags=["vCard"])

# ------------------------------------------------------------
# Для обратной совместимости со старым порталом
# ------------------------------------------------------------
# /vcard → старый эндпойнт, чтобы портал не ломался
app.include_router(qr_vcard.router, prefix="", tags=["Legacy vCard"])

# ============================================================
# Точка входа (для локального запуска)
# ============================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
