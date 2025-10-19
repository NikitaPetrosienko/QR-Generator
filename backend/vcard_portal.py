# ===== Импорты =====
from fastapi import APIRouter, Query, Request      # для роутера и параметров API
import os                                          # работа с окружением (VCARD_EXT_BASE)
import re                                          # регулярки (разбор ФИО, телефонов)

# Импорт из qr_core — функции для генерации QR и ответа
from backend.qr_core import (
    build_png_fixed_with_logo_and_finders,  # строим PNG с логотипом и цветными углами
    respond_fixed_png,                       # обёртка ответа с правильными заголовками
    style_signature,                         # принимает cfg
)

# Импорт загрузчика конфига
from config.config import load_all_config # переименовать папку конфиг

# ===== Создаём роутер =====
router = APIRouter()


# ======== Вспомогательные функции ========

def _v_escape(s: str) -> str:
    """
    Экранируем спецсимволы для vCard:
    - \ → \\
    - ; → \;
    - , → \,
    - переводы строк → \\n
    """
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace(";", r"\;")
    s = s.replace(",", r"\,")
    s = s.replace("\r\n", r"\n").replace("\n", r"\n").replace("\r", "")
    return s


def _join_crlf(lines) -> str:
    """Собираем строки карточки в один текст с CRLF (как требует стандарт vCard)."""
    return "\r\n".join(lines)


def _split_fio(fn: str):
    """
    Разбиваем ФИО одной строкой → на части (фамилия, имя, отчество).
    Пример: 'Иванов Иван Иванович' → ('Иванов', 'Иван', 'Иванович')
    """
    parts = re.split(r"\s+", (fn or "").strip())
    last = parts[0] if len(parts) >= 1 else ""
    first = parts[1] if len(parts) >= 2 else ""
    middle = parts[2] if len(parts) >= 3 else ""
    return last, first, middle


def _norm_phone_display(p: str) -> str:
    """
    Нормализуем телефон:
    - оставляем только цифры, +, пробелы, дефисы, скобки и запятые
    - убираем лишние символы
    """
    if not p:
        return ""
    return re.sub(r"[^0-9+\- (),]", "", str(p)).strip()


# Основной рабочий номер компании (можно задать через переменную окружения)
VCARD_EXT_BASE = os.getenv("VCARD_EXT_BASE", "+74957486424")


def _extract_ext_from_work_short(work_short: str) -> str:
    """
    Из строки типа '002-8480' достаём только последние 4 цифры.
    Это будет "доб." (добавочный номер).
    """
    digits = re.findall(r"\d", work_short or "")
    if not digits:
        return ""
    last4 = "".join(digits[-4:])
    return last4


# ======== Эндпоинт для vCard ========

@router.get("/qr/vcard")
def qr_vcard_fixed(
    request: Request,                                     # сам HTTP-запрос
    fn: str = Query(..., description="ФИО одной строкой"),
    org: str = Query("", description="Организация"),
    title: str = Query("", description="Должность"),
    dept: str = Query("", description="Подразделение"),
    email: str = Query("", description="Почта"),
    mobile: str = Query("", description="Мобильный"),
    work_short: str = Query("", description="Короткий рабочий, например 002-8042 (из него возьмём доб.)"),
    filename: str = Query("vcard_qr", description="Имя файла"),
    compat: str = Query("std", description="(не используется, оставлен для совместимости)"),
):
    """
    Генерация визитки vCard 3.0 (для iOS и Android):
    - корректное имя (N, FN, X-ABShowAs)
    - EMAIL (рабочая почта)
    - TEL (рабочий с добавочным)
    - TEL (короткий номер — «внутренний»)
    - TEL (мобильный)
    - Бизнес-поля (Организация, Должность, Подразделение) → в NOTE
    """

    # Разбираем ФИО на части
    last, first, middle = _split_fio(fn)

    # --- базовые строки vCard ---
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_v_escape(last)};{_v_escape(first)};{_v_escape(middle)};;",
        f"FN:{_v_escape(fn)}",              # полное имя
        "X-ABShowAs:PERSON",                # iOS-метка, что это человек (не компания)
    ]

    # --- почта ---
    if email:
        lines.append(f"EMAIL;TYPE=INTERNET;TYPE=WORK;TYPE=pref:{_v_escape(email)}")

    # --- рабочий с добавочным ---
    main_work_display = _norm_phone_display(VCARD_EXT_BASE)   # основной номер
    ext = _extract_ext_from_work_short(work_short)            # доб. номер
    if main_work_display:
        tel_line = _v_escape(main_work_display)
        if ext:
            tel_line += f",{_v_escape(ext)}"  # формат «+номер,доб.» (iOS понимает)
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE;TYPE=pref:{tel_line}")

    # --- внутренний (короткий) ---
    work_short_display = _norm_phone_display(work_short)
    if work_short_display:
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE:{_v_escape(work_short_display)}")

    # --- мобильный ---
    if mobile:
        lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{_v_escape(_norm_phone_display(mobile))}")

    # --- бизнес-поля (в NOTE, чтобы не было дублей на Android) ---
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

    # Завершаем карточку
    lines.append("END:VCARD")

    # Собираем финальный текст vCard
    vcard = _join_crlf(lines)

    # Генерим QR PNG фиксированного стиля
    png_bytes = build_png_fixed_with_logo_and_finders(vcard)

    # Загружаем свежий конфиг (каждый раз читаем json)
    cfg = load_all_config()

    # ETag: учитываем сам текст карточки, стиль и базовый номер
    etag_key = "|".join([
        vcard,
        style_signature(cfg),   
        f"extbase={VCARD_EXT_BASE}",
    ])

    # Возвращаем готовый PNG в HTTP-ответе
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=filename)
