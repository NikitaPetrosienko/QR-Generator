# backend/app/api/qr_router.py
import os, re
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, Request, Query, HTTPException

from backend.app.core.qr_core import (
    build_png_fixed_with_logo_and_finders,
    respond_fixed_png,
    style_signature,
    FIXED_SIZE,
    FIXED_BORDER,
)

router = APIRouter(prefix="/api/v1", tags=["QR"])

VCARD_EXT_BASE = os.getenv("VCARD_EXT_BASE", "+74957486424")

# --- утилиты vCard (оставляем твою логику) ---
def _v_escape(s: str) -> str:
    if not s:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,")
    s = s.replace("\r\n", r"\n").replace("\n", r"\n").replace("\r", "")
    return s

def _join_crlf(lines):
    return "\r\n".join(lines)

def _split_fio(fn: str):
    parts = re.split(r"\s+", (fn or "").strip())
    last  = parts[0] if len(parts) >= 1 else ""
    first = parts[1] if len(parts) >= 2 else ""
    mid   = parts[2] if len(parts) >= 3 else ""
    return last, first, mid

def _norm_phone_display(p: str) -> str:
    if not p:
        return ""
    return re.sub(r"[^0-9+\- (),]", "", str(p)).strip()

def _extract_ext_from_work_short(work_short: str) -> str:
    digits = re.findall(r"\d", work_short or "")
    return "".join(digits[-4:]) if digits else ""

def _mailto(to: str, subject: Optional[str], body: Optional[str]) -> str:
    if not to.strip():
        raise HTTPException(status_code=400, detail="Поле 'to' обязательно")
    q = []
    if subject:
        q.append(f"subject={quote(subject)}")
    if body:
        q.append(f"body={quote(body)}")
    return f"mailto:{to}" + (("?" + "&".join(q)) if q else "")

# --- один универсальный GET /api/v1/qr ---
@router.get("/qr")
def generate_qr(
    request: Request,
    # необязательный явный тип
    type: Optional[str] = Query(None, description="url | phone | mail | sms | vcard"),
    # общие кастомизации
    fill: str = Query("#000000"),
    finder: str = Query("#000000"),
    bg: str = Query("#FFFFFF"),
    filename: Optional[str] = Query(None),
    # возможные поля под разные типы
    data: Optional[str] = Query(None),          # url/text
    number: Optional[str] = Query(None),        # phone (вариант 1)
    phonenumber: Optional[str] = Query(None),   # phone (вариант 2)
    to: Optional[str] = Query(None),            # mail
    subject: Optional[str] = Query(None),
    body: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),         # sms
    text: Optional[str] = Query(None),
    fn: Optional[str] = Query(None),            # vcard
    org: Optional[str] = Query(""),
    dept: Optional[str] = Query(""),
    title: Optional[str] = Query(""),
    email: Optional[str] = Query(""),
    mobile: Optional[str] = Query(""),
    work_short: Optional[str] = Query(""),
):
    # 1) авто-детект, если type не указан
    # приоритет: vcard > mail > sms > phone > url
    if not type:
        if fn:
            type = "vcard"
        elif to:
            type = "mail"
        elif phone and (text is not None):
            type = "sms"
        elif (number or phonenumber):
            type = "phone"
        elif data:
            type = "url"
        else:
            raise HTTPException(status_code=400, detail="Нужно указать type или поля для одного из типов")
    type = type.lower().strip()

    # 2) сборка payload под нужный тип
    style = {"size": FIXED_SIZE, "border": FIXED_BORDER, "fill": fill, "bg": bg, "finder": finder}

    if type == "url":
        if not (data or "").strip():
            raise HTTPException(status_code=400, detail="Поле 'data' обязательно для url")
        qr_text = data
        default_name = "qr_url"
        etag_key = f"url|{qr_text}|{style_signature(style)}"

    elif type == "phone":
        num = (number or phonenumber or "").strip()
        if not num:
            raise HTTPException(status_code=400, detail="Поле 'number' (или phonenumber) обязательно для phone")
        qr_text = f"TEL:{num}"
        default_name = "qr_phone"
        etag_key = f"phone|{num}|{style_signature(style)}"

    elif type == "mail":
        qr_text = _mailto(to or "", subject, body)
        default_name = "qr_mail"
        etag_key = f"mail|{qr_text}|{style_signature(style)}"

    elif type == "sms":
        if not (phone or "").strip():
            raise HTTPException(status_code=400, detail="Поле 'phone' обязательно для sms")
        qr_text = f"SMSTO:{phone}:{text or ''}"
        default_name = "qr_sms"
        etag_key = f"sms|{phone}|{text or ''}|{style_signature(style)}"

    elif type == "vcard":
        if not (fn or "").strip():
            raise HTTPException(status_code=400, detail="Поле 'fn' обязательно для vcard")
        last, first, mid = _split_fio(fn)
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"N:{_v_escape(last)};{_v_escape(first)};{_v_escape(mid)};;",
            f"FN:{_v_escape(fn)}",
            "X-ABShowAs:PERSON",
        ]
        if email:
            lines.append(f"EMAIL;TYPE=INTERNET;TYPE=WORK;TYPE=pref:{_v_escape(email)}")

        main_work = _norm_phone_display(VCARD_EXT_BASE)
        ext = _extract_ext_from_work_short(work_short)
        if main_work:
            tel_line = _v_escape(main_work) + (f",{_v_escape(ext)}" if ext else "")
            lines.append(f"TEL;TYPE=WORK;TYPE=VOICE;TYPE=pref:{tel_line}")

        if work_short:
            lines.append(f"TEL;TYPE=WORK;TYPE=VOICE:{_v_escape(_norm_phone_display(work_short))}")
        if mobile:
            lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{_v_escape(_norm_phone_display(mobile))}")

        note = []
        if org:
            note.append(f"Организация: {org}")
        if title:
            note.append(f"Должность: {title}")
        if dept:
            note.append(f"Подразделение: {dept}")
        if note:
            # ВАЖНО: сначала считаем строку, потом подставляем
            note_text = "\\n".join(_v_escape(s) for s in note)
            lines.append(f"NOTE:{note_text}")

        lines.append("END:VCARD")
        qr_text = _join_crlf(lines)
        default_name = "vcard_qr"
        etag_key = f"vcard|{fn}|{style_signature(style)}|extbase={VCARD_EXT_BASE}"

    else:
        raise HTTPException(status_code=400, detail="Unknown type")

    # 3) рендер и ответ
    png = build_png_fixed_with_logo_and_finders(qr_text, fill=fill, bg=bg, finder=finder)
    return respond_fixed_png(
        request=request,
        data_key=etag_key,
        content=png,
        filename=(filename or default_name),
    )
