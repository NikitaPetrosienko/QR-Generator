import os
import re
from typing import Optional
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel

from backend.app.core.qr_core import (
    build_png_fixed_with_logo_and_finders,
    respond_fixed_png,
    style_signature,
    FIXED_SIZE,
    FIXED_BORDER,
)

router = APIRouter()

VCARD_EXT_BASE = os.getenv("VCARD_EXT_BASE", "+74957486424")


def _v_escape(s: str) -> str:
    if not s:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,")
    s = s.replace("\r\n", r"\n").replace("\n", r"\n").replace("\r", "")
    return s


def _join_crlf(lines) -> str:
    return "\r\n".join(lines)


def _split_fio(fn: str):
    parts = re.split(r"\s+", (fn or "").strip())
    last = parts[0] if len(parts) >= 1 else ""
    first = parts[1] if len(parts) >= 2 else ""
    middle = parts[2] if len(parts) >= 3 else ""
    return last, first, middle


def _norm_phone_display(p: str) -> str:
    if not p:
        return ""
    return re.sub(r"[^0-9+\- (),]", "", str(p)).strip()


def _extract_ext_from_work_short(work_short: str) -> str:
    digits = re.findall(r"\d", work_short or "")
    return "".join(digits[-4:]) if digits else ""


class VCardRequest(BaseModel):
    fn: str
    org: Optional[str] = ""
    title: Optional[str] = ""
    dept: Optional[str] = ""
    email: Optional[str] = ""
    mobile: Optional[str] = ""
    work_short: Optional[str] = ""
    filename: Optional[str] = "vcard_qr"


@router.get("/vcard")
def generate_vcard_get(
    request: Request,
    fn: str = Query(...),
    org: str = Query(""),
    title: str = Query(""),
    dept: str = Query(""),
    email: str = Query(""),
    mobile: str = Query(""),
    work_short: str = Query(""),
    filename: str = Query("vcard_qr"),
    fill: str = Query("#000000"),
    finder: str = Query("#000000"),
    bg: str = Query("#FFFFFF"),
):
    if not fn.strip():
        raise HTTPException(status_code=400, detail="Поле 'fn' обязательно к заполнению")
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

    main_work = _norm_phone_display(VCARD_EXT_BASE)
    ext = _extract_ext_from_work_short(work_short)
    if main_work:
        tel_line = _v_escape(main_work)
        if ext:
            tel_line += f",{_v_escape(ext)}"
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE;TYPE=pref:{tel_line}")

    if work_short:
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE:{_v_escape(_norm_phone_display(work_short))}")

    if mobile:
        lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{_v_escape(_norm_phone_display(mobile))}")

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
        fill=fill,
        bg=bg,
        finder=finder,
    )

    style = {"size": FIXED_SIZE, "border": FIXED_BORDER, "fill": fill, "bg": bg, "finder": finder}
    etag_key = f"vcard|{fn}|{style_signature(style)}|extbase={VCARD_EXT_BASE}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=filename)


@router.post("/vcard")
def generate_vcard_post(request: Request, payload: VCardRequest):
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

    main_work = _norm_phone_display(VCARD_EXT_BASE)
    ext = _extract_ext_from_work_short(payload.work_short)
    if main_work:
        tel_line = _v_escape(main_work)
        if ext:
            tel_line += f",{_v_escape(ext)}"
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE;TYPE=pref:{tel_line}")

    if payload.work_short:
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE:{_v_escape(_norm_phone_display(payload.work_short))}")

    if payload.mobile:
        lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{_v_escape(_norm_phone_display(payload.mobile))}")

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
        fill="#000000",
        bg="#FFFFFF",
        finder="#000000",
    )

    style = {"size": FIXED_SIZE, "border": FIXED_BORDER, "fill": "#000000", "bg": "#FFFFFF", "finder": "#000000"}
    etag_key = f"vcard|{payload.fn}|{style_signature(style)}|extbase={VCARD_EXT_BASE}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=payload.filename or "vcard_qr")
