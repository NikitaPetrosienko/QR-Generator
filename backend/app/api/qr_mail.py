"""
qr_mail.py — генерация QR-кода для email-ссылки (mailto:).
Позволяет при сканировании открыть окно "Написать письмо".
"""

from typing import Optional
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel, EmailStr
import urllib.parse  # важно — для корректного кодирования текста письма

from backend.app.core.qr_core import (
    build_png_fixed_with_logo_and_finders,
    respond_fixed_png,
    style_signature,
)

router = APIRouter()


# ============================================================
# МОДЕЛЬ ДАННЫХ (POST)
# ============================================================

class MailRequest(BaseModel):
    """Тело POST-запроса для генерации QR-кода почтовой ссылки."""
    to: EmailStr
    subject: Optional[str] = None
    body: Optional[str] = None
    filename: Optional[str] = "qr_mail"
    style: Optional[dict] = None  # {"fill":"#000","finder":"#000","bg":"#FFF","size":512,"border":8}


# ============================================================
# GET /qr/mail
# ============================================================

@router.get("/mail")
def generate_mail_qr_get(
    request: Request,
    to: str = Query(..., description="Адрес получателя"),
    subject: str = Query("", description="Тема письма"),
    body: str = Query("", description="Текст письма"),
    filename: str = Query("qr_mail", description="Имя файла без расширения"),
    # Кастомизация внешнего вида
    fill: str = Query("#000000", description="Цвет QR"),
    finder: str = Query("#000000", description="Цвет угловых квадратов"),
    bg: str = Query("#FFFFFF", description="Цвет фона"),
    size: int = Query(512, description="Размер изображения, px"),
    border: int = Query(8, description="Отступ (рамка) вокруг QR, px"),
):
    """Генерация QR-кода для e-mail (GET)."""
    # mailto:user@example.com?subject=Hi&body=Text
    mailto = f"mailto:{to}"
    params = []
    if subject:
        params.append(f"subject={urllib.parse.quote(subject)}")
    if body:
        params.append(f"body={urllib.parse.quote(body)}")
    if params:
        mailto += "?" + "&".join(params)

    # Генерация изображения с учётом кастомизации
    png_bytes = build_png_fixed_with_logo_and_finders(
        mailto,
        size=size,
        border=border,
        fill=fill,
        bg=bg,
        finder=finder,
    )

    style = {"size": size, "border": border, "fill": fill, "bg": bg, "finder": finder}
    etag_key = f"mail|{mailto}|{style_signature(style)}"

    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=filename)


# ============================================================
# POST /qr/mail
# ============================================================

@router.post("/mail")
def generate_mail_qr_post(request: Request, payload: MailRequest):
    """
    Генерация QR-кода для e-mail (POST).
    Можно задать тему, текст и стиль QR.
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

    # mailto:user@example.com?subject=Hi&body=Text
    mailto = f"mailto:{payload.to}"
    params = []
    if payload.subject:
        params.append(f"subject={urllib.parse.quote(payload.subject)}")
    if payload.body:
        params.append(f"body={urllib.parse.quote(payload.body)}")
    if params:
        mailto += "?" + "&".join(params)

    png_bytes = build_png_fixed_with_logo_and_finders(
        mailto,
        size=int(style["size"]),
        border=int(style["border"]),
        fill=str(style["fill"]),
        bg=str(style["bg"]),
        finder=str(style["finder"]),
    )

    etag_key = f"mail|{mailto}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=payload.filename or "qr_mail")
