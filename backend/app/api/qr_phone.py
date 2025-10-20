"""
qr_phone.py — генерация QR-кода для телефонного номера.
Позволяет быстро вызвать звонок при сканировании QR-кода.
"""

from typing import Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from backend.app.core.qr_core import (
    build_png_fixed_with_logo_and_finders,
    respond_fixed_png,
    style_signature,
)

router = APIRouter()


# =========================
# МОДЕЛЬ ДАННЫХ (POST)
# =========================

class PhoneRequest(BaseModel):
    """Тело POST-запроса для генерации QR-кода по телефону."""
    phone: str
    filename: Optional[str] = "qr_phone"
    # Кастомизация стиля (все поля опциональны)
    style: Optional[dict] = None  # {"fill":"#000","finder":"#000","bg":"#FFF","size":512,"border":8}


# =========================
# GET /qr/phone
# =========================

@router.get("/phone")
def generate_phone_qr_get(
    request: Request,
    number: str = Query(..., description="Телефонный номер (например +79991234567)"),
    filename: str = Query("qr_phone", description="Имя файла без расширения"),
    # Кастомизация (по умолчанию — классический Ч/Б)
    fill: str = Query("#000000", description="Цвет QR"),
    finder: str = Query("#000000", description="Цвет угловых квадратов"),
    bg: str = Query("#FFFFFF", description="Цвет фона"),
    size: int = Query(512, description="Размер изображения, px"),
    border: int = Query(8, description="Отступ (рамка) вокруг QR, px"),
):
    """Генерация QR-кода для телефона (GET)."""
    qr_data = f"TEL:{number}"

    png_bytes = build_png_fixed_with_logo_and_finders(
        qr_data,
        size=size,
        border=border,
        fill=fill,
        bg=bg,
        finder=finder,
    )

    style = {"size": size, "border": border, "fill": fill, "bg": bg, "finder": finder}
    etag_key = f"phone|{qr_data}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=filename)


# =========================
# POST /qr/phone
# =========================

@router.post("/phone")
def generate_phone_qr_post(request: Request, payload: PhoneRequest):
    """
    Генерация QR-кода для телефона (POST).
    Поддерживает кастомизацию через payload.style.
    """
    # Дефолтный стиль — ч/б
    style = {
        "fill": "#000000",
        "finder": "#000000",
        "bg": "#FFFFFF",
        "size": 512,
        "border": 8,
    }
    # Накладываем пользовательские значения, если пришли
    if payload.style:
        style.update({k: v for k, v in payload.style.items() if v is not None})

    qr_data = f"TEL:{payload.phone}"

    png_bytes = build_png_fixed_with_logo_and_finders(
        qr_data,
        size=int(style["size"]),
        border=int(style["border"]),
        fill=str(style["fill"]),
        bg=str(style["bg"]),
        finder=str(style["finder"]),
    )

    etag_key = f"phone|{qr_data}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=payload.filename or "qr_phone")
