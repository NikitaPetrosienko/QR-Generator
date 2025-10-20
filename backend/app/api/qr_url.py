"""
qr_url.py — эндпойнт генерации QR-кода по URL-ссылке.
Пример:
POST /qr/url
{
  "url": "https://intranet.zn.ru/page?id=123",
  "filename": "portal_link"
}
или
GET /qr/url?data=https://intranet.zn.ru&page=id123
"""

from fastapi import APIRouter, Request, Query
from pydantic import BaseModel, HttpUrl
from typing import Optional

from backend.app.core.qr_core import build_png_fixed_with_logo_and_finders
from backend.app.core.qr_core import respond_fixed_png, style_signature
from backend.app.config.config import load_all_config

import hashlib

router = APIRouter()


# ============================================================
# МОДЕЛИ ДАННЫХ
# ============================================================

class UrlRequest(BaseModel):
    """Тело POST-запроса для генерации QR-кода по ссылке."""
    url: HttpUrl
    filename: Optional[str] = "qr_url"


# ============================================================
# GET-ВАРИАНТ (удобно для <img src>)
# ============================================================

@router.get("/url")
def generate_url_qr(
    request: Request,
    data: str = Query(...),
    fill: str = Query("#000000"),
    finder: str = Query("#000000"),
    bg: str = Query("#FFFFFF"),
    size: int = Query(512),
    border: int = Query(8),
):
    png = build_png_fixed_with_logo_and_finders(
        data,
        fill=fill,
        finder=finder,
        bg=bg,
        size=size,
        border=border,
    )
    key = "|".join([data, style_signature(locals())])
    return respond_fixed_png(request, data_key=key, content=png, filename="qr_url")


# ============================================================
# POST-ВАРИАНТ (удобно для фронта)
# ============================================================

@router.post("/url")
def generate_url_qr_post(request: Request, payload: UrlRequest):
    """Генерация QR по ссылке (POST-запрос)."""
    cfg = load_all_config()

    # URL для кодирования
    data = payload.url

    # Генерация изображения
    png_bytes = build_png_fixed_with_logo_and_finders(data)

    # ETag для кэша
    etag_key = hashlib.sha256(f"url={data}|{style_signature(cfg)}".encode()).hexdigest()

    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=payload.filename)
