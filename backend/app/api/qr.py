import os
from typing import Optional
from urllib.parse import quote
from io import BytesIO

from fastapi import APIRouter, Request, Query, HTTPException
from PIL import Image  # для работы с in-memory логотипом (POST)

from backend.app.core.http import respond_png
from backend.app.core.etag import style_signature
from backend.app.core.renderer import render_qr_png
from backend.app.core.vcard import build_vcard_text
from backend.app.config.config import load_all_config  # JSON-стиль для ЛК
from backend.app.core.style import QRStyle  # <-- ВАЖНО: добавлен импорт

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

def _truthy(v: Optional[str]) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "on")

# -----------------------
# ЕДИНЫЙ endpoint (GET/POST)
# -----------------------

@router.api_route("/qr", methods=["GET", "POST"])
async def generate_qr(
    request: Request,

    # режим работы
    context: Optional[str] = Query(None, description="ui | lk"),

    # тип QR (для совместимости оставляем общий роутер)
    type: Optional[str] = Query(None, description="url | phone | mail | sms | vcard"),

    # визуальные параметры (ui-режим, GET/POST)
    fill: str = Query("#000000"),
    finder: str = Query("#000000"),
    bg: str = Query("#FFFFFF"),
    filename: Optional[str] = Query(None),

    # ДАННЫЕ ДЛЯ ОБЩЕГО КОНСТРУКТОРА (ui, GET/POST)
    data: Optional[str] = Query(None),          # url/text
    number: Optional[str] = Query(None),        # phone вариант 1
    phonenumber: Optional[str] = Query(None),   # phone вариант 2
    to: Optional[str] = Query(None),            # mail
    subject: Optional[str] = Query(None),
    body: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),         # sms
    text: Optional[str] = Query(None),

    # ПОЛЯ vCard (ui/lk, GET/POST)
    fn: Optional[str] = Query(None),
    org: Optional[str] = Query(""),
    dept: Optional[str] = Query(""),
    title: Optional[str] = Query(""),
    email: Optional[str] = Query(""),
    mobile: Optional[str] = Query(""),
    work_short: Optional[str] = Query(""),

    # Спец-режим: генерировать vCard только с коротким рабочим номером
    only_work_short: Optional[str] = Query(None, description="1|true|yes|on -> только короткий номер"),
):
    method = request.method.upper()

    # Если это POST — достанем form и переопределим значения полей из формы
    form = None
    if method == "POST":
        try:
            form = await request.form()
        except Exception:
            raise HTTPException(status_code=400, detail="Некорректное тело запроса (ожидается form-data)")

        # В LK-режиме POST не допускаем
        ctx_raw = (form.get("context") or context or "ui")
        if str(ctx_raw).lower() == "lk":
            raise HTTPException(status_code=405, detail="POST запрещён для context=lk")

        def _p(name: str, default: Optional[str] = None) -> Optional[str]:
            v = form.get(name)
            if v is None:
                # fallback к query (если кто-то кинет смешанно)
                return request.query_params.get(name, default)
            return str(v).strip()

        # Переопределяем значения из формы
        context = _p("context", context or "ui")
        type     = _p("type", type)
        fill     = _p("fill", fill)
        finder   = _p("finder", finder)
        bg       = _p("bg", bg)
        filename = _p("filename", filename)

        data        = _p("data", data)
        number      = _p("number", number)
        phonenumber = _p("phonenumber", phonenumber)
        to          = _p("to", to)
        subject     = _p("subject", subject)
        body        = _p("body", body)
        phone       = _p("phone", phone)
        text        = _p("text", text)

        fn         = _p("fn", fn)
        org        = _p("org", org)
        dept       = _p("dept", dept)
        title      = _p("title", title)
        email      = _p("email", email)
        mobile     = _p("mobile", mobile)
        work_short = _p("work_short", work_short)
        only_work_short = _p("only_work_short", only_work_short)

    # -----------------------
    # Определяем режим
    # -----------------------
    ctx = (context or "ui").lower()
    if ctx not in ("ui", "lk"):
        raise HTTPException(status_code=400, detail="context must be 'ui' or 'lk'")

    # -----------------------
    # LK: фиксированный стиль из JSON и параметры из query
    # -----------------------
    if ctx == "lk":
        if type and type.lower().strip() != "vcard":
            raise HTTPException(status_code=400, detail="В режиме 'lk' поддерживается только type=vcard")
        if method == "POST":
            raise HTTPException(status_code=405, detail="POST запрещён для context=lk")

        cfg = load_all_config()                    # читает backend/app/config/qr_config.json
        style = QRStyle.from_config(cfg)           # бренд-цвета, логотип, EC и т.п.

        # В LK больше НЕ используем VCARD_EXT_BASE — короткий + мобильный (если есть)
        profile = {
            "fn":         (fn or "").strip(),
            "org":        (org or "").strip(),
            "title":      (title or "").strip(),
            "dept":       (dept or "").strip(),
            "email":      (email or "").strip(),
            "mobile":     (mobile or "").strip(),
            "work_short": (work_short or "").strip(),
        }
        if not profile["fn"]:
            raise HTTPException(status_code=400, detail="В режиме 'lk' требуется параметр 'fn' (ФИО)")

        payload = build_vcard_text(
            fn=profile["fn"],
            org=profile.get("org", ""),
            title=profile.get("title", ""),
            dept=profile.get("dept", ""),
            email=profile.get("email", ""),
            mobile=profile.get("mobile", ""),
            work_short=profile.get("work_short", ""),
            only_work_short=False,
        )

        default_name = "vcard_qr"
        et_key = "|".join([payload, style_signature(style), "lk-mode=only-short"])
        png = render_qr_png(payload, style)  # LK-логотип приходит из style.logo_path
        return respond_png(request, data_key=et_key, content=png, filename=(filename or default_name))

    # -----------------------
    # UI: универсальный конструктор
    # -----------------------

    # Определяем тип, если не указан явно
    if not type:
        if fn: type = "vcard"
        elif to: type = "mail"
        elif phone and (text is not None): type = "sms"
        elif (number or phonenumber): type = "phone"
        elif data: type = "url"
        else:
            raise HTTPException(status_code=400, detail="Нужно указать type или поля для одного из типов")
    type = type.lower().strip()

    # Стиль для UI — без логотипа в стиле (даже если он есть в конфиге)
    style = QRStyle(size=512, border=8, fill=fill, bg=bg, finder=finder, ec="H", logo_path=None, logo_ratio=0.0)

    # Сборка payload + etag-ключа
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

        use_only_short = _truthy(only_work_short)

        if use_only_short:
            # только короткий номер
            payload = build_vcard_text(
                fn=fn, org=org, title=title, dept=dept,
                email=email, mobile="", work_short=(work_short or ""),
                only_work_short=True
            )
        else:
            # без городского: только короткий и мобильный (если заданы)
            payload = build_vcard_text(
                fn=fn, org=org, title=title, dept=dept,
                email=email, mobile=mobile, work_short=(work_short or ""),
                only_work_short=False
            )

        default_name = "vcard_qr"
        et_key = f"vcard|{fn}|{style_signature(style)}|only_short={int(use_only_short)}"

    else:
        raise HTTPException(status_code=400, detail="Unknown type")

    # -----------------------
    # Рендер: GET (без лого) или POST (с пользовательским логотипом)
    # -----------------------
    user_logo_image = None
    if method == "POST" and form is not None:
        upload = form.get("logo")
        if upload:
            try:
                # базовые проверки
                content_type = getattr(upload, "content_type", "") or ""
                if content_type.lower() != "image/png":
                    raise HTTPException(status_code=400, detail="Логотип должен быть PNG (image/png)")

                raw = await upload.read()
                if not raw:
                    raise HTTPException(status_code=400, detail="Файл логотипа пустой")
                if len(raw) > 500 * 1024:
                    raise HTTPException(status_code=400, detail="Размер логотипа должен быть ≤ 500 KB")

                # открываем как Pillow Image
                user_logo_image = Image.open(BytesIO(raw))
                user_logo_image.load()  # прогружаем в память

                # ограничим экстремальные размеры (пропорционально до 1024)
                max_side = 1024
                if user_logo_image.width > max_side or user_logo_image.height > max_side:
                    user_logo_image.thumbnail((max_side, max_side), Image.LANCZOS)

            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=400, detail="Не удалось прочитать файл логотипа (PNG)")

    png = render_qr_png(payload, style, logo_image=user_logo_image)
    return respond_png(request, data_key=et_key, content=png, filename=(filename or default_name))
