import hashlib
import unicodedata
import re
import urllib.parse
from io import BytesIO
from typing import Tuple

import qrcode
from qrcode.constants import ERROR_CORRECT_Q, ERROR_CORRECT_H
from PIL import Image, ImageDraw
from fastapi import Request, Response
from config.config import load_all_config


# ==================== ВСПОМОГАТЕЛЬНЫЕ ====================

def _file_hash(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "no-logo"


def style_signature(cfg: dict) -> str:
    return "|".join([
        f"size={cfg.get('QR_SIZE', 256)}",
        f"border_px={cfg.get('QR_BORDER_PX', cfg.get('QR_BORDER', 0))}",
        f"fill={cfg.get('QR_FILL', '#009639')}",
        f"bg={cfg.get('QR_BG', '#FFFFFF')}",
        f"finder={cfg.get('QR_FINDER', '#EAAA00')}",
        f"logo_hash={_file_hash(cfg.get('QR_LOGO', 'assets/logo.png'))}",
    ])


# HTTP 

def _safe_ascii_filename(name: str, default: str = "vcard_qr") -> str:
    base = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-")
    return base or default


def respond_fixed_png(request: Request, *, data_key: str, content: bytes, filename: str) -> Response:
    etag = hashlib.sha256(data_key.encode("utf-8")).hexdigest()
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)
    ascii_name = _safe_ascii_filename(filename) + ".png"
    utf8_name = urllib.parse.quote((filename or "vcard_qr") + ".png", safe="")
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}',
    }
    return Response(content=content, media_type="image/png", headers=headers)


# ГЕНЕРАЦИЯ QR 

def _generate_qr_image_fixed(
    data: str,
    size_px: int,
    border_px: int,
    eclevel,
    fill: str,
    bg: str
) -> Tuple[Image.Image, int, int, Tuple[int, int]]:
    """
    Генерирует QR строго фиксированного размера.
    Без «встроенных» модульных бордеров, всё подчинено size_px и border_px.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=eclevel,
        box_size=1,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)

    modules = qr.modules_count

    
    qr_area = size_px - 2 * border_px
    box_size = qr_area / modules 
    qr_img = qr.make_image(fill_color=fill, back_color=bg).convert("RGBA")

    # рескейлим QR ровно под нужный размер, чтобы убрать лишние поля
    target_size = int(modules * box_size)
    qr_img = qr_img.resize((target_size, target_size), Image.NEAREST)

    canvas = Image.new("RGBA", (size_px, size_px), bg)
    canvas.paste(qr_img, (border_px, border_px))
    return canvas, int(box_size), modules, (border_px, border_px)


def _recolor_finders_precise(
    img: Image.Image,
    box: int,
    modules: int,
    color: str,
    bg: str,
    offset=(0, 0)
):
    
    draw = ImageDraw.Draw(img)
    offx, offy = offset
    total_size = img.width - 2 * offx
    actual_box = total_size / modules

    def rect(mx, my, w, h, fill):
        x0 = offx + mx * actual_box
        y0 = offy + my * actual_box
        x1 = x0 + w * actual_box
        y1 = y0 + h * actual_box
        draw.rectangle([x0, y0, x1, y1], fill=fill)

    for (mx, my) in [(0, 0), (modules - 7, 0), (0, modules - 7)]:
        rect(mx, my, 7, 7, color)
        rect(mx + 1, my + 1, 5, 5, bg)
        rect(mx + 2, my + 2, 3, 3, color)



def _paste_logo_with_pad(
    img: Image.Image,
    logo_path: str,
    ratio: float,
    pad_scale: float,
    pad_radius: int,
    pad_color: str
) -> Image.Image:
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except Exception:
        return img

    side = min(img.size)
    target = max(1, int(side * ratio))
    logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size

    if pad_scale and pad_scale != 1.0:
        pad_w = int(lw * pad_scale)
        pad_h = int(lh * pad_scale)
        pad = Image.new("RGBA", (pad_w, pad_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(pad)
        d.rounded_rectangle([0, 0, pad_w - 1, pad_h - 1], radius=pad_radius, fill=pad_color)
        cx = (img.width - pad_w) // 2
        cy = (img.height - pad_h) // 2
        img.paste(pad, (cx, cy), pad)
        lx = cx + (pad_w - lw) // 2
        ly = cy + (pad_h - lh) // 2
    else:
        lx = (img.width - lw) // 2
        ly = (img.height - lh) // 2

    img.paste(logo, (lx, ly), logo)
    return img


def build_png_fixed_with_logo_and_finders(data: str) -> bytes:
    """Финальная сборка QR."""
    cfg = load_all_config()
    size = int(cfg.get("QR_SIZE", 256))
    border_px = int(cfg.get("QR_BORDER_PX", cfg.get("QR_BORDER", 0)))
    fill = cfg.get("QR_FILL", "#000000")
    bg = cfg.get("QR_BG", "#FFFFFF")
    finder = cfg.get("QR_FINDER", "#EAAA00")
    logo_path = cfg.get("QR_LOGO", "assets/logo.png")
    logo_ratio = float(cfg.get("QR_LOGO_RATIO", 0.5))
    logo_pad = float(cfg.get("QR_LOGO_PAD", 0.5))
    logo_pad_radius = int(cfg.get("QR_LOGO_PAD_RADIUS", 0))
    eclevel = ERROR_CORRECT_H if str(cfg.get("QR_EC", "H")).upper() == "H" else ERROR_CORRECT_Q

    img, box, modules, offset = _generate_qr_image_fixed(
        data, size, border_px, eclevel, fill, bg
    )
    _recolor_finders_precise(img, box, modules, finder, bg, offset)
    img = _paste_logo_with_pad(img, logo_path, logo_ratio, logo_pad, logo_pad_radius, bg)

    out = BytesIO()
    img.convert("RGB").save(out, format="PNG")
    return out.getvalue()
