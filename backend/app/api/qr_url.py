import hashlib
from typing import Optional

from fastapi import APIRouter, Request, Query
from pydantic import BaseModel, HttpUrl

from backend.app.core.qr_core import (
    build_png_fixed_with_logo_and_finders,
    respond_fixed_png,
    style_signature,
    FIXED_SIZE,
    FIXED_BORDER,
)

router = APIRouter()


# ============================================================
# МОДЕЛЬ ДАННЫХ
# ============================================================

class UrlRequest(BaseModel):
    """Тело POST-запроса для генерации QR-кода по ссылке."""
    url: HttpUrl
    filename: Optional[str] = "qr_url"


# ============================================================
# GET /qr/url
# ============================================================

@router.get("/url")
def generate_url_qr_get(
    request: Request,
    data: str = Query(..., description="Ссылка или произвольный текст для кодирования"),
    fill: str = Query("#000000", description="Цвет QR"),
    finder: str = Query("#000000", description="Цвет угловых квадратов"),
    bg: str = Query("#FFFFFF", description="Цвет фона"),
):
    if not data.strip():
        raise HTTPException(status_code=400, detail="Поле data' обязательно к заполнению")
    """
    Генерация QR-кода для URL (GET).
    Подходит для вставки в <img src="...">.
    """
    png = build_png_fixed_with_logo_and_finders(
        data,
        fill=fill,
        finder=finder,
        bg=bg,
    )

    style = {
        "size": FIXED_SIZE,
        "border": FIXED_BORDER,
        "fill": fill,
        "bg": bg,
        "finder": finder,
    }

    etag_key = f"url|{data}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png, filename="qr_url")


# ============================================================
# POST /qr/url
# ============================================================

@router.post("/url")
def generate_url_qr_post(request: Request, payload: UrlRequest):
    """
    Генерация QR-кода для URL (POST).
    Удобно использовать из фронта (отправка JSON).
    """
    data = str(payload.url)

    png_bytes = build_png_fixed_with_logo_and_finders(data)

    style = {
        "size": FIXED_SIZE,
        "border": FIXED_BORDER,
        "fill": "#000000",
        "bg": "#FFFFFF",
        "finder": "#000000",
    }

    etag_key = hashlib.sha256(f"url|{data}|{style_signature(style)}".encode()).hexdigest()
    return respond_fixed_png(
        request,
        data_key=etag_key,
        content=png_bytes,
        filename=payload.filename or "qr_url",
    )
