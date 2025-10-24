from typing import Optional
from urllib.parse import quote, unquote
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel, EmailStr

from backend.app.core.qr_core import (
    build_png_fixed_with_logo_and_finders,
    respond_fixed_png,
    style_signature,
    FIXED_SIZE,
    FIXED_BORDER,
)

router = APIRouter()


class MailRequest(BaseModel):
    to: EmailStr
    subject: Optional[str] = None
    body: Optional[str] = None
    filename: Optional[str] = "qr_mail"


@router.get("/mail")
def generate_mail_qr_get(
    request: Request,
    to: str = Query(...),
    subject: str = Query(""),
    body: str = Query(""),
    filename: str = Query("qr_mail"),
    fill: str = Query("#000000"),
    finder: str = Query("#000000"),
    bg: str = Query("#FFFFFF"),
):
    if not to.strip():
        raise HTTPException(status_code=400, detail="Поле 'to' обязательно к заполнению")
    mailto = f"mailto:{to}"
    params = []
    if subject:
        params.append(f"subject={quote(subject)}")
    if body:
        params.append(f"body={quote(body)}")
    if params:
        mailto += "?" + "&".join(params)

    png_bytes = build_png_fixed_with_logo_and_finders(
        mailto,
        fill=fill,
        bg=bg,
        finder=finder,
    )

    style = {"size": FIXED_SIZE, "border": FIXED_BORDER, "fill": fill, "bg": bg, "finder": finder}
    etag_key = f"mail|{mailto}|{style_signature(style)}"
    return respond_fixed_png(request, data_key=etag_key, content=png_bytes, filename=filename)