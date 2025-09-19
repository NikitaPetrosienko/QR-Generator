# vcard_portal.py
from fastapi import APIRouter, Query, Request
from qr_core import (
    build_png_fixed_with_logo_and_finders,
    respond_fixed_png,
    STYLE_SIGNATURE,
)
import os
import re

router = APIRouter()

# --------- helpers ---------
def _v_escape(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,")
    s = s.replace("\r\n", r"\n").replace("\n", r"\n").replace("\r", "")
    return s

def _join_crlf(lines) -> str:
    return "\r\n".join(lines)

def _split_fio(fn: str):
    parts = re.split(r"\s+", (fn or "").strip())
    last  = parts[0] if len(parts) >= 1 else ""
    first = parts[1] if len(parts) >= 2 else ""
    middle= parts[2] if len(parts) >= 3 else ""
    return last, first, middle

def _only_digits_plus(p: str) -> str:
    if not p:
        return ""
    return re.sub(r"[^0-9+\- (),]", "", str(p)).strip()

VCARD_EXT_BASE = os.getenv("VCARD_EXT_BASE", "+74957486424")

def _ext_from_work_short(work_short: str) -> str:
    # из "002-8480" вытаскиваем последние 4 цифры -> "8480"
    digits = re.findall(r"\d", work_short or "")
    return "".join(digits[-4:]) if digits else ""

# --------- vCard builders ---------
def _build_vcard_ios(fn, org, title, dept, email, mobile, work_short):
    last, first, middle = _split_fio(fn)
    main_work = _only_digits_plus(VCARD_EXT_BASE)
    ext = _ext_from_work_short(work_short)
    work_short_display = _only_digits_plus(work_short)

    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_v_escape(last)};{_v_escape(first)};{_v_escape(middle)};;",
        f"FN:{_v_escape(fn)}",
        "X-ABShowAs:PERSON",
    ]

    org_line = f"ORG:{_v_escape(org)}"
    if dept:
        org_line += f";{_v_escape(dept)}"
    lines.append(org_line)
    if title:
        lines.append(f"TITLE:{_v_escape(title)}")
        lines.append(f"ROLE:{_v_escape(title)}")

    if email:
        lines.append(f"EMAIL;TYPE=INTERNET;TYPE=WORK;TYPE=pref:{_v_escape(email)}")

    # Рабочий c добавочным в ОДНОМ поле (iOS красиво показывает "...,8042")
    if main_work:
        work_with_ext = main_work + (f",{ext}" if ext else "")
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE;TYPE=pref:{_v_escape(work_with_ext)}")

    # Отдельно "Внутренний" с яблочным лайблом (Android это игнорирует — поэтому только в iOS-профиле)
    if work_short_display:
        lines.append(f"item1.TEL:{_v_escape(work_short_display)}")
        lines.append("item1.X-ABLabel:Внутренний")

    if mobile:
        lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{_v_escape(_only_digits_plus(mobile))}")

    # дубли текста в NOTE, чтобы точно отобразилось на iOS
    note_parts = []
    if org:   note_parts.append(f"Организация: {org}")
    if title: note_parts.append(f"Должность: {title}")
    if dept:  note_parts.append(f"Подразделение: {dept}")
    if note_parts:
        note_text = "\\n".join(_v_escape(s) for s in note_parts)
        lines.append(f"NOTE:{note_text}")

    lines.append("END:VCARD")
    return _join_crlf(lines)

def _build_vcard_android(fn, org, title, dept, email, mobile, work_short):
    last, first, middle = _split_fio(fn)
    main_work = _only_digits_plus(VCARD_EXT_BASE)
    work_short_display = _only_digits_plus(work_short)

    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_v_escape(last)};{_v_escape(first)};{_v_escape(middle)};;",
        f"FN:{_v_escape(fn)}",
    ]

    org_line = f"ORG:{_v_escape(org)}"
    if dept:
        org_line += f";{_v_escape(dept)}"
    lines.append(org_line)
    if title:
        lines.append(f"TITLE:{_v_escape(title)}")

    if email:
        lines.append(f"EMAIL;TYPE=INTERNET;TYPE=WORK;TYPE=pref:{_v_escape(email)}")

    # Рабочий БЕЗ добавочного (Android не показывает запятую нормально)
    if main_work:
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE;TYPE=pref:{_v_escape(main_work)}")

    # Внутренний отдельной строкой, чтобы был виден как второй номер
    if work_short_display:
        lines.append(f"TEL;TYPE=OTHER:{_v_escape(work_short_display)}")

    if mobile:
        lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{_v_escape(_only_digits_plus(mobile))}")

    # на Android и так видны поля ниже, NOTE оставим для единообразия
    note_parts = []
    if org:   note_parts.append(f"Организация: {org}")
    if title: note_parts.append(f"Должность: {title}")
    if dept:  note_parts.append(f"Подразделение: {dept}")
    if note_parts:
        note_text = "\\n".join(_v_escape(s) for s in note_parts)
        lines.append(f"NOTE:{note_text}")

    lines.append("END:VCARD")
    return _join_crlf(lines)

# --------- endpoint ---------
@router.get("/qr/vcard")
def qr_vcard_fixed(
    request: Request,
    fn: str = Query(..., description="ФИО одной строкой"),
    org: str = Query(..., description="Организация"),
    title: str = Query("", description="Должность"),
    dept: str = Query("", description="Подразделение"),
    email: str = Query("", description="Почта"),
    mobile: str = Query("", description="Мобильный"),
    work_short: str = Query("", description="Короткий рабочий, например 002-8042"),
    os: str = Query("ios", pattern="^(ios|android)$", description="Профиль вкарды: ios|android"),
    filename: str = Query("vcard_qr", description="Имя файла"),
):
    """
    Два профиля:

    - os=ios:
        * Рабочий:   +74957486424,8042
        * Внутрений: item1.TEL + item1.X-ABLabel:Внутренний
    - os=android:
        * Рабочий:   +74957486424
        * Внутренний: TEL;TYPE=OTHER: 002-84-80
    Общие поля: N/FN, ORG(+dept), TITLE/ROLE (в iOS), EMAIL, CELL, NOTE (дубли текста).
    """
    if os == "ios":
        vcard = _build_vcard_ios(fn, org, title, dept, email, mobile, work_short)
    else:
        vcard = _build_vcard_android(fn, org, title, dept, email, mobile, work_short)

    png = build_png_fixed_with_logo_and_finders(vcard)
    etag_key = "|".join([vcard, STYLE_SIGNATURE, f"os={os}", f"extbase={VCARD_EXT_BASE}"])
    return respond_fixed_png(request, data_key=etag_key, content=png, filename=filename)
