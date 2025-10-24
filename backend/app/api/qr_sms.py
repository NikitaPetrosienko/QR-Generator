from typing import Optional
from urllib.parse import unquote
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


class SMSRequest(BaseModel):
    phone: str
    text: Optional[str] = ""
    filename: Optional[str] = "qr_sms"


import urllib.parse

@router.get("/sms")
def generate_sms_qr_get(
    request: Request,
    phone: str = Query(..., description="Номер получателя"),
    text: str = Query("", description="Текст SMS"),
    filename: str = Query("qr_sms", description="Имя файла"),
    fill: str = Query("#000000"),
    finder: str = Query("#000000"),
    bg: str = Query("#FFFFFF"),
):
    if not phone.strip():
        raise HTTPException(status_code=400, detail="Поле 'phone' обязательно к заполнению")
    """Генерация QR-кода для SMS (GET)."""
    decoded_text = urllib.parse.unquote(text or "")
    sms_data = f"SMSTO:{phone}:{decoded_text}"

    png_bytes = build_png_fixed_with_logo_and_finders(
        sms_data,
        fill=fill,
        bg=bg,
        finder=finder,
    )

    style = {"size": 512, "border": 8, "fill": fill, "bg": bg, "finder": finder}
    etag_key = f"sms|{sms_data}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=filename)