# backend/app/api/qr.py
import os
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Request, Query, HTTPException

from backend.app.core.http import respond_png
from backend.app.core.style import QRStyle, vcard_ext_base_from_env_or_cfg
from backend.app.core.etag import style_signature
from backend.app.core.renderer import render_qr_png
from backend.app.core.vcard import build_vcard_text
from backend.app.config.config import load_all_config  # JSON-стиль для ЛК

router = APIRouter(prefix="/api/v1", tags=["QR"])

# -----------------------
# Вспомогательные
# -----------------------

def _mailto(to: str, subject: Optional[str], body: Optional[str]) -> str:
    if not to or not to.strip():
        raise HTTPException(status_code=400, detail="Поле 'to' обязательно")
    q = []
    if subject: q.append(f"subject={quote(subject)}")
    if body:    q.append(f"body={quote(body)}")
    return f"mailto:{to}" + (("?" + "&".join(q)) if q else "")

def _decode_header(val: str) -> str:
    """Корректно декодирует кириллицу из заголовков (Latin-1 → UTF-8)."""
    if not val:
        return ""
    try:
        # если кириллица закодирована как ISO-8859-1, перекодируем в UTF-8
        return val.encode("latin1").decode("utf-8")
    except Exception:
        # если уже нормальная строка, просто возвращаем
        return val.strip()

def _get_lk_profile(request: Request) -> dict:
    """Читает данные из заголовков X-Employee-* и безопасно декодирует кириллицу."""
    h = request.headers
    return {
        "fn":         _decode_header(h.get("X-Employee-FullName")),
        "org":        _decode_header(h.get("X-Employee-Org")),
        "title":      _decode_header(h.get("X-Employee-Title")),
        "dept":       _decode_header(h.get("X-Employee-Dept")),
        "email":      _decode_header(h.get("X-Employee-Email")),
        "mobile":     _decode_header(h.get("X-Employee-Mobile")),
        "work_short": _decode_header(h.get("X-Employee-WorkShort")),
    }

# -----------------------
# ЕДИНЫЙ endpoint
# -----------------------

@router.get("/qr")
def generate_qr(
    request: Request,

    # режим работы
    context: Optional[str] = Query(None, description="ui | lk"),

    # тип QR (для совместимости оставляем общий роутер)
    type: Optional[str] = Query(None, description="url | phone | mail | sms | vcard"),

    # визуальные параметры (ui-режим)
    fill: str = Query("#000000"),
    finder: str = Query("#000000"),
    bg: str = Query("#FFFFFF"),
    filename: Optional[str] = Query(None),

    # ДАННЫЕ ДЛЯ ОБЩЕГО КОНСТРУКТОРА (ui)
    data: Optional[str] = Query(None),          # url/text
    number: Optional[str] = Query(None),        # phone вариант 1
    phonenumber: Optional[str] = Query(None),   # phone вариант 2
    to: Optional[str] = Query(None),            # mail
    subject: Optional[str] = Query(None),
    body: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),         # sms
    text: Optional[str] = Query(None),

    # ПОЛЯ vCard (ui-режим)
    fn: Optional[str] = Query(None),
    org: Optional[str] = Query(""),
    dept: Optional[str] = Query(""),
    title: Optional[str] = Query(""),
    email: Optional[str] = Query(""),
    mobile: Optional[str] = Query(""),
    work_short: Optional[str] = Query(""),
):
    # -----------------------
    # Определяем режим
    # -----------------------
    ctx = (context or "ui").lower()
    if ctx not in ("ui", "lk"):
        raise HTTPException(status_code=400, detail="context must be 'ui' or 'lk'")

    # -----------------------
    # Определяем тип QR
    # -----------------------
    if not type:
        # авто-детект как было
        if fn: type = "vcard"
        elif to: type = "mail"
        elif phone and (text is not None): type = "sms"
        elif (number or phonenumber): type = "phone"
        elif data: type = "url"
        else:
            # если явно сказали context=lk, считаем type=vcard
            if ctx == "lk":
                type = "vcard"
            else:
                raise HTTPException(status_code=400, detail="Нужно указать type или поля для одного из типов")
    type = type.lower().strip()

    # -----------------------
    # Ветвление по контексту
    # -----------------------

    # ====== LK: фиксированный стиль из JSON и данные сотрудника с бэка ======
    if ctx == "lk":
        if type != "vcard":
            raise HTTPException(status_code=400, detail="В режиме 'lk' поддерживается только type=vcard")

        cfg = load_all_config()                    # читает backend/app/config/qr_config.json
        style = QRStyle.from_config(cfg)           # бренд-цвета, логотип, EC и т.п.
        ext_base = vcard_ext_base_from_env_or_cfg(cfg)

        profile = _get_lk_profile(request)         # тут будет вызов твоего ЛК
        if not profile.get("fn"):
            raise HTTPException(status_code=400, detail="В режиме 'lk' требуется ФИО (см. интеграцию с ЛК)")

        payload = build_vcard_text(
            fn=profile["fn"],
            org=profile.get("org", ""),
            title=profile.get("title", ""),
            dept=profile.get("dept", ""),
            email=profile.get("email", ""),
            mobile=profile.get("mobile", ""),
            work_short=profile.get("work_short", ""),
            ext_base=ext_base,
        )

        default_name = "vcard_qr"
        et_key = "|".join([payload, style_signature(style), f"extbase={ext_base}"])
        png = render_qr_png(payload, style)
        return respond_png(request, data_key=et_key, content=png, filename=(filename or default_name))

    # ====== UI: как было (универсальный конструктор), логотип ОТКЛЮЧЕН ======
    style = QRStyle(size=512, border=8, fill=fill, bg=bg, finder=finder, ec="H", logo_path=None, logo_ratio=0.0)

    if type == "url":
        if not (data or "").strip():
            raise HTTPException(status_code=400, detail="Поле 'data' обязательно для url")
        payload = data
        default_name = "qr_url"
        et_key = f"url|{payload}|{style_signature(style)}"

    elif type == "phone":
        num = (number or phonenumber or "").strip()
        if not num:
            raise HTTPException(status_code=400, detail="Поле 'number' (или phonenumber) обязательно для phone")
        payload = f"TEL:{num}"
        default_name = "qr_phone"
        et_key = f"phone|{num}|{style_signature(style)}"

    elif type == "mail":
        payload = _mailto(to or "", subject, body)
        default_name = "qr_mail"
        et_key = f"mail|{payload}|{style_signature(style)}"

    elif type == "sms":
        if not (phone or "").strip():
            raise HTTPException(status_code=400, detail="Поле 'phone' обязательно для sms")
        payload = f"SMSTO:{phone}:{text or ''}"
        default_name = "qr_sms"
        et_key = f"sms|{phone}|{text or ''}|{style_signature(style)}"

    elif type == "vcard":
        if not (fn or "").strip():
            raise HTTPException(status_code=400, detail="Поле 'fn' обязательно для vcard")
        ext_base = vcard_ext_base_from_env_or_cfg({})
        payload = build_vcard_text(
            fn=fn, org=org, title=title, dept=dept, email=email, mobile=mobile, work_short=work_short, ext_base=ext_base
        )
        default_name = "vcard_qr"
        et_key = f"vcard|{fn}|{style_signature(style)}|extbase={ext_base}"

    else:
        raise HTTPException(status_code=400, detail="Unknown type")

    png = render_qr_png(payload, style)
    return respond_png(request, data_key=et_key, content=png, filename=(filename or default_name))
