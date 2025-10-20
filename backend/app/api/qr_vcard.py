"""
qr_vcard.py — генерация QR-кода визитки (vCard 3.0)
Используется для обмена контактами на iOS / Android.
Поддерживает GET (/vcard) и POST (/vcard) с кастомизацией.
"""

from typing import Optional
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel
import re

from backend.app.core.qr_core import (
    build_png_fixed_with_logo_and_finders,
    respond_fixed_png,
    style_signature,
)

router = APIRouter()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def _v_escape(s: str) -> str:
    """Экранируем спецсимволы для vCard."""
    if not s:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,")
    s = s.replace("\r\n", r"\n").replace("\n", r"\n").replace("\r", "")
    return s


def _split_fio(fn: str):
    """Разбиваем строку ФИО на (фамилия, имя, отчество)."""
    parts = re.split(r"\s+", (fn or "").strip())
    last = parts[0] if len(parts) >= 1 else ""
    first = parts[1] if len(parts) >= 2 else ""
    middle = parts[2] if len(parts) >= 3 else ""
    return last, first, middle


def _join_crlf(lines) -> str:
    """Собираем строки карточки с CRLF (стандарт vCard)."""
    return "\r\n".join(lines)


# ============================================================
# МОДЕЛЬ POST-ЗАПРОСА
# ============================================================

class VCardRequest(BaseModel):
    """Тело POST-запроса для генерации vCard."""
    fn: str
    org: Optional[str] = ""
    title: Optional[str] = ""
    dept: Optional[str] = ""
    email: Optional[str] = ""
    mobile: Optional[str] = ""
    work_short: Optional[str] = ""
    filename: Optional[str] = "vcard_qr"
    style: Optional[dict] = None  # {"fill":"#000","finder":"#000","bg":"#FFF","size":512,"border":8}


# ============================================================
# GET /vcard
# ============================================================

@router.get("/vcard")
def generate_vcard_get(
    request: Request,
    fn: str = Query(..., description="ФИО одной строкой"),
    org: str = Query("", description="Организация"),
    title: str = Query("", description="Должность"),
    dept: str = Query("", description="Подразделение"),
    email: str = Query("", description="Почта"),
    mobile: str = Query("", description="Мобильный телефон"),
    work_short: str = Query("", description="Короткий рабочий, например 002-8042"),
    filename: str = Query("vcard_qr", description="Имя файла"),
    # Кастомизация
    fill: str = Query("#000000", description="Цвет QR"),
    finder: str = Query("#000000", description="Цвет угловых квадратов"),
    bg: str = Query("#FFFFFF", description="Цвет фона"),
    size: int = Query(512, description="Размер изображения, px"),
    border: int = Query(8, description="Отступ (рамка) вокруг QR, px"),
):
    """Генерация QR-кода с визиткой (GET)."""

    last, first, middle = _split_fio(fn)

    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_v_escape(last)};{_v_escape(first)};{_v_escape(middle)};;",
        f"FN:{_v_escape(fn)}",
        "X-ABShowAs:PERSON",
    ]

    if email:
        lines.append(f"EMAIL;TYPE=INTERNET;TYPE=WORK;TYPE=pref:{_v_escape(email)}")
    if mobile:
        lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{_v_escape(mobile)}")
    if work_short:
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE:{_v_escape(work_short)}")

    note_parts = []
    if org:
        note_parts.append(f"Организация: {org}")
    if title:
        note_parts.append(f"Должность: {title}")
    if dept:
        note_parts.append(f"Подразделение: {dept}")
    if note_parts:
        note_text = "\\n".join(_v_escape(s) for s in note_parts)
        lines.append(f"NOTE:{note_text}")

    lines.append("END:VCARD")
    vcard_text = _join_crlf(lines)

    png_bytes = build_png_fixed_with_logo_and_finders(
        vcard_text,
        size=size,
        border=border,
        fill=fill,
        bg=bg,
        finder=finder,
    )

    style = {"size": size, "border": border, "fill": fill, "bg": bg, "finder": finder}
    etag_key = f"vcard|{fn}|{style_signature(style)}"

    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=filename)


# ============================================================
# POST /vcard
# ============================================================

@router.post("/vcard")
def generate_vcard_post(request: Request, payload: VCardRequest):
    """Генерация QR-кода vCard (POST) с кастомизацией."""
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

    last, first, middle = _split_fio(payload.fn)

    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_v_escape(last)};{_v_escape(first)};{_v_escape(middle)};;",
        f"FN:{_v_escape(payload.fn)}",
        "X-ABShowAs:PERSON",
    ]

    if payload.email:
        lines.append(f"EMAIL;TYPE=INTERNET;TYPE=WORK;TYPE=pref:{_v_escape(payload.email)}")
    if payload.mobile:
        lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{_v_escape(payload.mobile)}")
    if payload.work_short:
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE:{_v_escape(payload.work_short)}")

    note_parts = []
    if payload.org:
        note_parts.append(f"Организация: {payload.org}")
    if payload.title:
        note_parts.append(f"Должность: {payload.title}")
    if payload.dept:
        note_parts.append(f"Подразделение: {payload.dept}")
    if note_parts:
        note_text = "\\n".join(_v_escape(s) for s in note_parts)
        lines.append(f"NOTE:{note_text}")

    lines.append("END:VCARD")
    vcard_text = _join_crlf(lines)

    png_bytes = build_png_fixed_with_logo_and_finders(
        vcard_text,
        size=int(style["size"]),
        border=int(style["border"]),
        fill=str(style["fill"]),
        bg=str(style["bg"]),
        finder=str(style["finder"]),
    )

    etag_key = f"vcard|{payload.fn}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=payload.filename or "vcard_qr")
