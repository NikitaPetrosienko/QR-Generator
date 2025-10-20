import os
import re
from fastapi import APIRouter, Query, Request

from backend.qr_core import (
    build_png_fixed_with_logo_and_finders,
    respond_fixed_png,
    style_signature,
)
from config.config import load_all_config

router = APIRouter()

# Основной рабочий номер (можно задать через переменную окружения)
VCARD_EXT_BASE = os.getenv("VCARD_EXT_BASE", "+74957486424")


def _v_escape(s: str) -> str:
    """Экранируем спецсимволы для vCard."""
    if not s:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,")
    s = s.replace("\r\n", r"\n").replace("\n", r"\n").replace("\r", "")
    return s


def _join_crlf(lines) -> str:
    """Собираем строки карточки с CRLF (стандарт vCard)."""
    return "\r\n".join(lines)


def _split_fio(fn: str):
    """Разбиваем строку ФИО на (фамилия, имя, отчество)."""
    parts = re.split(r"\s+", (fn or "").strip())
    last = parts[0] if len(parts) >= 1 else ""
    first = parts[1] if len(parts) >= 2 else ""
    middle = parts[2] if len(parts) >= 3 else ""
    return last, first, middle


def _norm_phone_display(p: str) -> str:
    """Нормализуем телефон — оставляем цифры, +, пробелы, дефисы, скобки."""
    if not p:
        return ""
    return re.sub(r"[^0-9+\- (),]", "", str(p)).strip()


def _extract_ext_from_work_short(work_short: str) -> str:
    """Из строки типа '002-8480' достаём последние 4 цифры (добавочный)."""
    digits = re.findall(r"\d", work_short or "")
    return "".join(digits[-4:]) if digits else ""


# Основной эндпоинт

@router.get("/vcard")
def generate_vcard(
    request: Request,
    fn: str = Query(..., description="ФИО одной строкой"),
    org: str = Query("", description="Организация"),
    title: str = Query("", description="Должность"),
    dept: str = Query("", description="Подразделение"),
    email: str = Query("", description="Почта"),
    mobile: str = Query("", description="Мобильный телефон"),
    work_short: str = Query("", description="Короткий рабочий, например 002-8042"),
    filename: str = Query("vcard_qr", description="Имя файла"),
):
    """Формирует визитку vCard 3.0 и возвращает её в виде QR-кода PNG."""

    # Разбираем ФИО
    last, first, middle = _split_fio(fn)

    # Собираем строки vCard
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_v_escape(last)};{_v_escape(first)};{_v_escape(middle)};;",
        f"FN:{_v_escape(fn)}",
        "X-ABShowAs:PERSON",
    ]

    # Почта
    if email:
        lines.append(f"EMAIL;TYPE=INTERNET;TYPE=WORK;TYPE=pref:{_v_escape(email)}")

    # Рабочий с добавочным
    main_work = _norm_phone_display(VCARD_EXT_BASE)
    ext = _extract_ext_from_work_short(work_short)
    if main_work:
        tel_line = _v_escape(main_work)
        if ext:
            tel_line += f",{_v_escape(ext)}"
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE;TYPE=pref:{tel_line}")

    # Внутренний короткий
    if work_short:
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE:{_v_escape(_norm_phone_display(work_short))}")

    # Мобильный
    if mobile:
        lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{_v_escape(_norm_phone_display(mobile))}")

    # Бизнес-поля в NOTE
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

    # Финальная карточка
    vcard_text = _join_crlf(lines)

    # Генерируем QR
    png_bytes = build_png_fixed_with_logo_and_finders(vcard_text)
    cfg = load_all_config()

    # ETag с учётом данных и стиля
    etag_key = "|".join([vcard_text, style_signature(cfg), f"extbase={VCARD_EXT_BASE}"])

    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=filename)
