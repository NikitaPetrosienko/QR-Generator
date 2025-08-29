from fastapi import FastAPI, Query, Response, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import qrcode, qrcode.image.svg
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from io import BytesIO
import hashlib

app = FastAPI(title="QR Generator", version="1.0.0")

# На проде сузим до домена портала, сейчас оставлю * для локалки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

LEVELS = {"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ERROR_CORRECT_H}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/qr")
def generate_qr(
    request: Request,
    data: str = Query(..., description="Данные для кодирования (текст/URL/vCard и т.п.)"),
    format: str = Query("png", pattern="^(png|svg)$"),
    size: int = Query(512, ge=64, le=2048, description="Размер PNG в пикселях"),
    level: str = Query("M", pattern="^[LMQH]$", description="Уровень коррекции ошибок"),
    margin: int = Query(2, ge=0, le=8, description="Отступ (модули)"),
    download: int = Query(0, ge=0, le=1, description="1 — скачать файлом, 0 — inline"),
    filename: str = Query("qr", description="Имя файла без расширения")
):
    # Ограничим длину для GET 
    if len(data) > 4000:
        raise HTTPException(status_code=413, detail="data слишком длинный для GET; используйте короче или POST (можно добавить позже)")

    # Кэш-ключ
    key = f"{data}|{format}|{size}|{level}|{margin}"
    etag = hashlib.sha256(key.encode("utf-8")).hexdigest()
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)

    if format == "svg":
        factory = qrcode.image.svg.SvgImage
        img = qrcode.make(data, image_factory=factory, border=margin)
        buf = BytesIO(); img.save(buf)
        content, media, ext = buf.getvalue(), "image/svg+xml", "svg"
    else:
        qr = qrcode.QRCode(version=None, error_correction=LEVELS[level], box_size=10, border=margin)
        qr.add_data(data); qr.make(fit=True)
        pil = qr.make_image(fill_color="black", back_color="white").resize((size, size))
        buf = BytesIO(); pil.save(buf, format="PNG")
        content, media, ext = buf.getvalue(), "image/png", "png"

    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{filename}.{ext}"'
    }
    return Response(content=content, media_type=media, headers=headers)
