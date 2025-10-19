import hashlib                   # библиотека для хэширования (используем для ETag кэширования)
from io import BytesIO           # буфер для хранения байтов (PNG/SVG картинок в памяти)

import qrcode                    # основная библиотека для генерации QR-кодов
import qrcode.image.svg          # подключаем поддержку формата SVG через фабрику
from qrcode.constants import ERROR_CORRECT_Q  # константа: уровень коррекции ошибок "Q"

# Импорты из FastAPI
from fastapi import FastAPI, Query, Response, HTTPException, Request  # базовые классы и типы
from fastapi.middleware.cors import CORSMiddleware                    # middleware для CORS
from fastapi.staticfiles import StaticFiles                           # для раздачи статики (html, js, css)
from pydantic import BaseModel, Field                                 # для валидации входных/выходных данных

# Импорт роутера для vCard (отдельный модуль)
from backend.vcard_portal import router as vcard_router


# ===== Инициализация приложения =====

# Создаём объект FastAPI, это API-приложение
app = FastAPI(
    title="QR Generator",    # название приложения (будет видно в документации Swagger)
    version="1.4.1"          # версия API (будет видно в Swagger)
)


# ===== Настройка CORS =====

# Добавляем middleware для CORS (чтобы фронтенд с другого домена мог делать запросы)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В проде заменить "*" на конкретный домен портала
    allow_methods=["GET", "POST", "OPTIONS"],  # какие методы разрешены
    allow_headers=["*"],  # какие заголовки разрешены
)


# ===== Healthcheck =====

@app.get("/healthz")   # эндпоинт GET /healthz
def healthz():
    """Проверка, что сервис живой (для Docker healthcheck)."""
    return {"status": "ok"}  # всегда возвращаем JSON {"status": "ok"}


# ===== Спецификация форм для UI =====

# Константа, описывающая какие типы QR поддерживаются и какие поля нужны
FORM_SPEC = {
    "types": [  # список поддерживаемых типов QR
        {"key": "url",   "label": "Ссылка"},
        {"key": "text",  "label": "Текст"},
        {"key": "tel",   "label": "Телефон"},
        {"key": "email", "label": "Email"},
        {"key": "sms",   "label": "SMS"},
        {"key": "wifi",  "label": "Wi-Fi"},
        {"key": "vcard", "label": "vCard"},
    ],
    "fields": {  # словарь: для каждого типа указываем список полей
        "url":   [{"key": "url", "label": "URL", "type": "text", "required": True,
                   "placeholder": "https://example.com"}],
        "text":  [{"key": "text", "label": "Текст", "type": "textarea", "required": True}],
        "tel":   [{"key": "number", "label": "Телефон", "type": "text", "required": True,
                   "placeholder": "+79991234567"}],
        "email": [{"key": "email", "label": "Email", "type": "text", "required": True,
                   "placeholder": "user@company.ru"}],
        "sms": [
            {"key": "number", "label": "Номер", "type": "text", "required": True,
             "placeholder": "+79991234567"},
            {"key": "body", "label": "Текст", "type": "text", "required": False,
             "placeholder": "Здравствуйте…"}
        ],
        "wifi": [
            {"key": "auth", "label": "Безопасность", "type": "select",
             "options": ["WPA", "WEP", "nopass"], "required": True},
            {"key": "ssid", "label": "SSID", "type": "text", "required": True},
            {"key": "password", "label": "Пароль", "type": "text", "required": False},
            {"key": "hidden", "label": "Скрытая сеть", "type": "checkbox", "required": False}
        ],
        "vcard": [
            {"key": "last", "label": "Фамилия", "type": "text", "required": False},
            {"key": "first", "label": "Имя", "type": "text", "required": False},
            {"key": "middle", "label": "Отчество", "type": "text", "required": False},
            {"key": "fn", "label": "Полное имя (FN)", "type": "text", "required": False,
             "placeholder": "Если пусто — соберём из Имя+Фамилия"},
            {"key": "org", "label": "Организация", "type": "text", "required": False,
             "placeholder": "ЗН Цифра"},
            {"key": "title", "label": "Должность", "type": "text", "required": False},
            {"key": "tel", "label": "Телефон", "type": "text", "required": False},
            {"key": "email", "label": "Email", "type": "text", "required": False},
            {"key": "url", "label": "Сайт", "type": "text", "required": False},
            {"key": "note", "label": "Заметка", "type": "text", "required": False}
        ]
    },
    "qr_params": {  # параметры генерации QR
        "format": ["png", "svg"],
        "size":   {"min": 64, "max": 2048, "default": 512},
        "margin": {"min": 0,  "max": 8,    "default": 2},
        "colors_supported_for_png": True
    }
}

@app.get("/form-spec")   # эндпоинт GET /form-spec
def form_spec():
    """Эндпоинт: возвращает описание доступных типов QR и их полей для фронтенда."""
    return FORM_SPEC


# ===== Составление строки для QR =====

# Модель запроса для /compose
class ComposeRequest(BaseModel):
    qr_type: str = Field(..., description="url|text|tel|email|sms|wifi|vcard")
    fields: dict  # словарь с полями, специфичными для типа

# Модель ответа для /compose
class ComposeResponse(BaseModel):
    data: str  # готовая строка для кодирования


def _compose(req: ComposeRequest) -> str:
    """Собираем строку для QR по заданному типу."""

    # Подготавливаем словарь полей (обрезаем пробелы у строк)
    fields = {
        k: (v or "").strip() if isinstance(v, str) else v
        for k, v in req.fields.items()
    }

    # Функции для каждого типа QR ----------------------
    def make_url():
        return fields.get("url", "")

    def make_text():
        return fields.get("text", "")

    def make_tel():
        return f"TEL:{fields.get('number', '')}"

    def make_email():
        return f"mailto:{fields.get('email', '')}"

    def make_sms():
        number = fields.get("number", "")
        body = fields.get("body", "")
        return f"SMSTO:{number}:{body}" if body else f"SMSTO:{number}"

    def make_wifi():
        auth = fields.get("auth", "WPA")
        ssid = fields.get("ssid", "")
        password = fields.get("password", "")
        hidden = 'H:true;' if fields.get("hidden") else ''
        return f"WIFI:T:{auth};S:{ssid};{'' if auth == 'nopass' else 'P:'+password+';'}{hidden};"

    def make_vcard():
        last = fields.get("last", "")
        first = fields.get("first", "")
        middle = fields.get("middle", "")
        fn = fields.get("fn") or (" ".join([first, last]).strip())
        org = fields.get("org", "")
        title = fields.get("title", "")
        tel = fields.get("tel", "")
        email = fields.get("email", "")
        url = fields.get("url", "")
        note = fields.get("note", "")

        # Составляем список строк vCard
        parts = [
            "BEGIN:VCARD", "VERSION:3.0",
            f"N:{last};{first};{middle};;",
            f"FN:{fn}" if fn else None,
            f"ORG:{org}" if org else None,
            f"TITLE:{title}" if title else None,
            f"TEL;TYPE=CELL:{tel}" if tel else None,
            f"EMAIL;TYPE=INTERNET:{email}" if email else None,
            f"URL:{url}" if url else None,
            f"NOTE:{note}" if note else None,
            "END:VCARD",
        ]
        # Склеиваем только непустые строки
        return "\n".join([p for p in parts if p])

    # Словарь "тип → генератор строки"
    generators = {
        "url": make_url,
        "text": make_text,
        "tel": make_tel,
        "email": make_email,
        "sms": make_sms,
        "wifi": make_wifi,
        "vcard": make_vcard,
    }

    # Пытаемся найти подходящий генератор
    try:
        return generators[req.qr_type]()
    except KeyError:
        raise HTTPException(400, f"Unknown type: {req.qr_type}")


@app.post("/compose", response_model=ComposeResponse)  # эндпоинт POST /compose
def compose(req: ComposeRequest):
    """Принимает поля и возвращает готовую строку для QR."""
    return ComposeResponse(data=_compose(req))


# ===== Генерация QR-кодов =====

def _build_png(data: str, size: int, margin: int, fill: str, back: str) -> bytes:
    """Генерация QR в PNG."""
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_Q,
                       box_size=10, border=margin)  # создаём объект QR-кода
    qr.add_data(data)     # добавляем данные
    qr.make(fit=True)     # оптимизируем размер
    img = qr.make_image(fill_color=fill, back_color=back) \
            .convert("RGB") \
            .resize((size, size))  # генерируем PNG и масштабируем под размер
    buf = BytesIO()       # создаём буфер в памяти
    img.save(buf, format="PNG")  # сохраняем картинку в буфер
    return buf.getvalue()  # возвращаем байты PNG


def _build_svg(data: str, margin: int) -> bytes:
    """Генерация QR в SVG."""
    factory = qrcode.image.svg.SvgImage   # фабрика для SVG
    img = qrcode.make(data, image_factory=factory, border=margin)  # генерим картинку
    buf = BytesIO()        # создаём буфер
    img.save(buf)          # сохраняем в буфер
    return buf.getvalue()  # возвращаем байты SVG


def _respond(request: Request, *, data: str, fmt: str, size: int, margin: int,
             fill: str, back: str, download: int, filename: str):
    """Формируем HTTP-ответ с QR-картинкой."""

    # Уникальный ключ для ETag (чтобы браузер мог кэшировать)
    key = f"{data}|{fmt}|{size}|{margin}|{fill}|{back}"
    etag = hashlib.sha256(key.encode("utf-8")).hexdigest()

    # Если клиент прислал тот же ETag → говорим "ничего не изменилось"
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)

    # Генерация картинки в зависимости от формата
    if fmt == "svg":
        content, media, ext = _build_svg(data, margin), "image/svg+xml", "svg"
    else:
        content, media, ext = _build_png(data, size, margin, fill, back), "image/png", "png"

    # Заголовки ответа
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=31536000, immutable",  # кэшируем на год
        "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{filename}.{ext}"',
    }

    # Возвращаем HTTP-ответ
    return Response(content=content, media_type=media, headers=headers)


@app.get("/qr")  # эндпоинт GET /qr
def qr_get(
    request: Request,
    data: str = Query(..., description="Готовая строка для кодирования"),
    format: str = Query("png", pattern="^(png|svg)$"),
    size: int = Query(512, ge=64, le=2048),
    margin: int = Query(2, ge=0, le=8),
    download: int = Query(0, ge=0, le=1),
    filename: str = Query("qr"),
    fill_color: str = Query("black"),
    back_color: str = Query("white"),
):
    """Эндпоинт: генерация QR через GET-запрос."""
    if len(data) > 4000:
        raise HTTPException(413, "Слишком длинно для GET; используй POST /qr")
    return _respond(request, data=data, fmt=format, size=size, margin=margin,
                    fill=fill_color, back=back_color, download=download, filename=filename)


# Pydantic-модель для POST /qr
class QrBody(BaseModel):
    data: str
    format: str = "png"
    size: int = 512
    margin: int = 2
    download: int = 0
    filename: str = "qr"
    fill_color: str = "black"
    back_color: str = "white"


@app.post("/qr")  # эндпоинт POST /qr
def qr_post(request: Request, body: QrBody):
    """Эндпоинт: генерация QR через POST-запрос (удобно для больших данных)."""
    return _respond(request, data=body.data, fmt=body.format, size=body.size, margin=body.margin,
                    fill=body.fill_color, back=body.back_color,
                    download=body.download, filename=body.filename)


# ===== Роуты для vCard =====

# Подключаем отдельный роутер с эндпоинтами для генерации визиток
app.include_router(vcard_router)


# ===== Раздача статики =====

# Раздаём содержимое папки public/ на адресе /ui
# Например, public/index.html будет доступен по адресу http://host/ui/index.html
app.mount("/ui", StaticFiles(directory="frontend", html=True), name="static")
