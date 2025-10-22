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


class PhoneRequest(BaseModel):
    phone: str
    filename: Optional[str] = "qr_phone"


@router.get("/phone")
def generate_phone_qr_get(
    request: Request,
    number: str = Query(...),
    filename: str = Query("qr_phone"),
    fill: str = Query("#000000"),
    finder: str = Query("#000000"),
    bg: str = Query("#FFFFFF"),
):
    qr_data = f"TEL:{number}"
    png_bytes = build_png_fixed_with_logo_and_finders(
        qr_data,
        fill=fill,
        bg=bg,
        finder=finder,
    )
    style = {"size": FIXED_SIZE, "border": FIXED_BORDER, "fill": fill, "bg": bg, "finder": finder}
    etag_key = f"phone|{qr_data}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=filename)


@router.post("/phone")
def generate_phone_qr_post(request: Request, payload: PhoneRequest):
    qr_data = f"TEL:{payload.phone}"
    png_bytes = build_png_fixed_with_logo_and_finders(
        qr_data,
        fill="#000000",
        bg="#FFFFFF",
        finder="#000000",
    )
    style = {"size": FIXED_SIZE, "border": FIXED_BORDER, "fill": "#000000", "bg": "#FFFFFF", "finder": "#000000"}
    etag_key = f"phone|{qr_data}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=payload.filename or "qr_phone")
