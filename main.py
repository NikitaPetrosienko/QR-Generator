from fastapi import FastAPI, Query, Response, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import qrcode, qrcode.image.svg
from qrcode.constants import ERROR_CORRECT_Q
from io import BytesIO
import hashlib

# наши роуты для портала (vCard)
from vcard_portal import router as vcard_router

app = FastAPI(title="QR Generator", version="1.4.1")

# ------------------------ CORS / HEALTH ------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # в проде — ограничь доменом портала
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# ------------------------ FORM SPEC (как было) ------------------------
FORM_SPEC = {
    "types": [
        {"key": "url",   "label": "Ссылка"},
        {"key": "text",  "label": "Текст"},
        {"key": "tel",   "label": "Телефон"},
        {"key": "email", "label": "Email"},
        {"key": "sms",   "label": "SMS"},
        {"key": "wifi",  "label": "Wi-Fi"},
        {"key": "vcard", "label": "vCard"},
    ],
    "fields": {
        "url":   [{"key":"url","label":"URL","type":"text","required":True,"placeholder":"https://example.com"}],
        "text":  [{"key":"text","label":"Текст","type":"textarea","required":True}],
        "tel":   [{"key":"number","label":"Телефон","type":"text","required":True,"placeholder":"+79991234567"}],
        "email": [{"key":"email","label":"Email","type":"text","required":True,"placeholder":"user@company.ru"}],
        "sms": [
            {"key":"number","label":"Номер","type":"text","required":True,"placeholder":"+79991234567"},
            {"key":"body","label":"Текст","type":"text","required":False,"placeholder":"Здравствуйте…"}
        ],
        "wifi": [
            {"key":"auth","label":"Безопасность","type":"select","options":["WPA","WEP","nopass"],"required":True},
            {"key":"ssid","label":"SSID","type":"text","required":True},
            {"key":"password","label":"Пароль","type":"text","required":False},
            {"key":"hidden","label":"Скрытая сеть","type":"checkbox","required":False}
        ],
        "vcard": [
            {"key":"last","label":"Фамилия","type":"text","required":False},
            {"key":"first","label":"Имя","type":"text","required":False},
            {"key":"middle","label":"Отчество","type":"text","required":False},
            {"key":"fn","label":"Полное имя (FN)","type":"text","required":False,"placeholder":"Если пусто — соберём из Имя+Фамилия"},
            {"key":"org","label":"Организация","type":"text","required":False,"placeholder":"ЗН Цифра"},
            {"key":"title","label":"Должность","type":"text","required":False},
            {"key":"tel","label":"Телефон","type":"text","required":False},
            {"key":"email","label":"Email","type":"text","required":False},
            {"key":"url","label":"Сайт","type":"text","required":False},
            {"key":"note","label":"Заметка","type":"text","required":False}
        ]
    },
    "qr_params": {
        "format": ["png","svg"],
        "size":   {"min":64, "max":2048, "default":512},
        "margin": {"min":0,  "max":8,    "default":2},
        "colors_supported_for_png": True
    }
}

@app.get("/form-spec")
def form_spec():
    return FORM_SPEC

# ------------------------ COMPOSE (как было) ------------------------
class ComposeRequest(BaseModel):
    type: str = Field(..., description="url|text|tel|email|sms|wifi|vcard")
    fields: dict

class ComposeResponse(BaseModel):
    data: str

def _compose(req: ComposeRequest) -> str:
    t = req.type
    f = {k: (v or "").strip() if isinstance(v, str) else v for k,v in req.fields.items()}
    if t == "url":
        return f.get("url","")
    if t == "text":
        return f.get("text","")
    if t == "tel":
        return f"TEL:{f.get('number','')}"
    if t == "email":
        return f"mailto:{f.get('email','')}"
    if t == "sms":
        n = f.get("number",""); b=f.get("body","")
        return f"SMSTO:{n}:{b}" if b else f"SMSTO:{n}"
    if t == "wifi":
        T=f.get("auth","WPA"); S=f.get("ssid",""); P=f.get("password",""); H='H:true;' if f.get("hidden") else ''
        return f"WIFI:T:{T};S:{S};{'' if T=='nopass' else 'P:'+P+';'}{H};"
    if t == "vcard":
        last=f.get("last",""); first=f.get("first",""); middle=f.get("middle","")
        fn=f.get("fn") or (" ".join([first,last]).strip())
        org=f.get("org",""); title=f.get("title",""); tel=f.get("tel",""); email=f.get("email","")
        url=f.get("url",""); note=f.get("note","")
        parts = [
            "BEGIN:VCARD","VERSION:3.0",
            f"N:{last};{first};{middle};;",
            f"FN:{fn}" if fn else None,
            f"ORG:{org}" if org else None,
            f"TITLE:{title}" if title else None,
            f"TEL;TYPE=CELL:{tel}" if tel else None,
            f"EMAIL;TYPE=INTERNET:{email}" if email else None,
            f"URL:{url}" if url else None,
            f"NOTE:{note}" if note else None,
            "END:VCARD"
        ]
        return "\n".join([p for p in parts if p is not None])
    raise HTTPException(400, f"Unknown type: {t}")

@app.post("/compose", response_model=ComposeResponse)
def compose(req: ComposeRequest):
    return ComposeResponse(data=_compose(req))

# ------------------------ Универсальный /qr (как было) ------------------------
def _build_png(data: str, size: int, margin: int, fill: str, back: str) -> bytes:
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_Q, box_size=10, border=margin)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color=fill, back_color=back).convert("RGB").resize((size, size))
    buf = BytesIO(); img.save(buf, format="PNG")
    return buf.getvalue()

def _build_svg(data: str, margin: int) -> bytes:
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(data, image_factory=factory, border=margin)
    buf = BytesIO(); img.save(buf)
    return buf.getvalue()

def _respond(request: Request, *, data: str, fmt: str, size: int, margin: int,
             fill: str, back: str, download: int, filename: str):
    key = f"{data}|{fmt}|{size}|{margin}|{fill}|{back}"
    etag = hashlib.sha256(key.encode("utf-8")).hexdigest()
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)
    if fmt == "svg":
        content, media, ext = _build_svg(data, margin), "image/svg+xml", "svg"
    else:
        content, media, ext = _build_png(data, size, margin, fill, back), "image/png", "png"
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{filename}.{ext}"',
    }
    return Response(content=content, media_type=media, headers=headers)

@app.get("/qr")
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
    if len(data) > 4000:
        raise HTTPException(413, "Слишком длинно для GET; используй POST /qr")
    return _respond(request, data=data, fmt=format, size=size, margin=margin,
                    fill=fill_color, back=back_color, download=download, filename=filename)

class QrBody(BaseModel):
    data: str
    format: str = "png"
    size: int = 512
    margin: int = 2
    download: int = 0
    filename: str = "qr"
    fill_color: str = "black"
    back_color: str = "white"

@app.post("/qr")
def qr_post(request: Request, body: QrBody):
    return _respond(request, data=body.data, fmt=body.format, size=body.size, margin=body.margin,
                    fill=body.fill_color, back=body.back_color,
                    download=body.download, filename=body.filename)

# ------------------------ ЛК vCard ------------------------
app.include_router(vcard_router)

# ------------------------ Статика ------------------------
app.mount("/ui", StaticFiles(directory="public", html=True), name="static")
