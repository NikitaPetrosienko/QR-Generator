"""
qr_sms.py — генерация QR-кода для отправки SMS.
Формат стандарта: SMSTO:+79991234567:Привет!
"""

from typing import Optional
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel

from backend.app.core.qr_core import (
    build_png_fixed_with_logo_and_finders,
    respond_fixed_png,
    style_signature,
)

router = APIRouter()


# ============================================================
# МОДЕЛЬ ДАННЫХ (POST)
# ============================================================

class SMSRequest(BaseModel):
    """Тело POST-запроса для генерации QR-кода SMS."""
    phone: str
    text: Optional[str] = ""
    filename: Optional[str] = "qr_sms"
    style: Optional[dict] = None  # {"fill":"#000","finder":"#000","bg":"#FFF","size":512,"border":8}


# ============================================================
# GET /qr/sms
# ============================================================

@router.get("/sms")
def generate_sms_qr_get(
    request: Request,
    phone: str = Query(..., description="Номер получателя (например +79991234567)"),
    text: str = Query("", description="Текст SMS"),
    filename: str = Query("qr_sms", description="Имя файла без расширения"),
    # Кастомизация внешнего вида
    fill: str = Query("#000000", description="Цвет QR"),
    finder: str = Query("#000000", description="Цвет угловых квадратов"),
    bg: str = Query("#FFFFFF", description="Цвет фона"),
    size: int = Query(512, description="Размер изображения, px"),
    border: int = Query(8, description="Отступ (рамка) вокруг QR, px"),
):
    """Генерация QR-кода для SMS (GET)."""
    sms_data = f"SMSTO:{phone}:{text or ''}"

    png_bytes = build_png_fixed_with_logo_and_finders(
        sms_data,
        size=size,
        border=border,
        fill=fill,
        bg=bg,
        finder=finder,
    )

    style = {"size": size, "border": border, "fill": fill, "bg": bg, "finder": finder}
    etag_key = f"sms|{sms_data}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=filename)


# ============================================================
# POST /qr/sms
# ============================================================

@router.post("/sms")
def generate_sms_qr_post(request: Request, payload: SMSRequest):
    """
    Генерация QR-кода для SMS (POST).
    Можно передать текст и кастомный стиль QR.
    """
    # Базовый стиль (по умолчанию — ч/б)
    style = {
        "fill": "#000000",
        "finder": "#000000",
        "bg": "#FFFFFF",
        "size": 512,
        "border": 8,
    }
    if payload.style:
        style.update({k: v for k, v in payload.style.items() if v is not None})

    sms_data = f"SMSTO:{payload.phone}:{payload.text or ''}"

    png_bytes = build_png_fixed_with_logo_and_finders(
        sms_data,
        size=int(style["size"]),
        border=int(style["border"]),
        fill=str(style["fill"]),
        bg=str(style["bg"]),
        finder=str(style["finder"]),
    )

    etag_key = f"sms|{sms_data}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=payload.filename or "qr_sms")
