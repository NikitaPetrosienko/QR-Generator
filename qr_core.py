import os, hashlib, unicodedata, re, urllib.parse
from io import BytesIO
from typing import Tuple

import qrcode
from qrcode.constants import ERROR_CORRECT_Q, ERROR_CORRECT_H
from PIL import Image, ImageDraw
from fastapi import Request, Response

# ===== стиль/дефолты (под Android и презентации) =====
QR_FIXED_SIZE = int(os.getenv("QR_SIZE", "768"))                     # побольше по умолчанию
QR_FIXED_BORDER = int(os.getenv("QR_BORDER", "3"))                   # тише зона 3 модуля
QR_FIXED_FILL = os.getenv("QR_FILL", "#009639")                      # модули
QR_FIXED_BG = os.getenv("QR_BG", "#FFFFFF")                          # фон
QR_FIXED_FINDER = os.getenv("QR_FINDER", "#EAAA00")                  # угловые ключи

QR_FIXED_LOGO_PATH = os.getenv("QR_LOGO", "assets/logo.png")
QR_FIXED_LOGO_RATIO = float(os.getenv("QR_LOGO_RATIO", "0.34"))      # аккуратный размер лого
QR_FIXED_LOGO_PAD = float(os.getenv("QR_LOGO_PAD", "0.5"))          # тонкая подложка
QR_FIXED_LOGO_PAD_RADIUS = int(os.getenv("QR_LOGO_PAD_RADIUS", "12"))

QR_FIXED_ECLEVEL = ERROR_CORRECT_H if os.getenv("QR_EC", "H").upper() == "H" else ERROR_CORRECT_Q

def _file_hash(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "no-logo"

QR_FIXED_LOGO_HASH = _file_hash(QR_FIXED_LOGO_PATH)

STYLE_SIGNATURE = "|".join([
    f"size={QR_FIXED_SIZE}",
    f"border={QR_FIXED_BORDER}",
    f"fill={QR_FIXED_FILL}",
    f"bg={QR_FIXED_BG}",
    f"finder={QR_FIXED_FINDER}",
    f"logo={QR_FIXED_LOGO_PATH}",
    f"logo_hash={QR_FIXED_LOGO_HASH}",
    f"logo_ratio={QR_FIXED_LOGO_RATIO}",
    f"logo_pad={QR_FIXED_LOGO_PAD}",
    f"ec={'H' if QR_FIXED_ECLEVEL == ERROR_CORRECT_H else 'Q'}",
])

# ===== filename/content-disposition =====
def _safe_ascii_filename(name: str, default: str = "vcard_qr") -> str:
    base = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-")
    return base or default

def respond_fixed_png(request: Request, *, data_key: str, content: bytes, filename: str):
    etag = hashlib.sha256(data_key.encode("utf-8")).hexdigest()
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)
    ascii_name = _safe_ascii_filename(filename, "vcard_qr") + ".png"
    utf8_name = urllib.parse.quote((filename or "vcard_qr") + ".png", safe="")
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}',
    }
    return Response(content=content, media_type="image/png", headers=headers)

# ===== рендер: модульность, ровные ключи, лого =====
def _compute_box_and_modules(data: str, margin_modules: int) -> Tuple[Image.Image, int, int, Tuple[int, int]]:
    qr_tmp = qrcode.QRCode(version=None, error_correction=QR_FIXED_ECLEVEL, box_size=1, border=margin_modules)
    qr_tmp.add_data(data); qr_tmp.make(fit=True)
    modules = qr_tmp.modules_count
    total_modules = modules + margin_modules * 2
    box_size = max(1, QR_FIXED_SIZE // total_modules)

    qr = qrcode.QRCode(version=None, error_correction=QR_FIXED_ECLEVEL, box_size=box_size, border=margin_modules)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color=QR_FIXED_FILL, back_color=QR_FIXED_BG).convert("RGBA")

    offset = (0, 0)
    if img.size[0] != QR_FIXED_SIZE:
        canvas = Image.new("RGBA", (QR_FIXED_SIZE, QR_FIXED_SIZE), QR_FIXED_BG)
        offset = ((QR_FIXED_SIZE - img.size[0]) // 2, (QR_FIXED_SIZE - img.size[1]) // 2)
        canvas.paste(img, offset)
        img = canvas
    return img, box_size, modules, offset

def _recolor_finders_precise(img: Image.Image, box: int, margin: int, modules: int, color: str, bg: str, offset=(0, 0)):
    draw = ImageDraw.Draw(img)
    offx, offy = offset
    def rect(mod_x, mod_y, w_mods, h_mods, fill):
        x0 = offx + (margin + mod_x) * box
        y0 = offy + (margin + mod_y) * box
        x1 = x0 + w_mods * box - 1
        y1 = y0 + h_mods * box - 1
        draw.rectangle([x0, y0, x1, y1], fill=fill)
    for mod_x, mod_y in [(0,0), (modules-7,0), (0,modules-7)]:
        rect(mod_x,     mod_y,     7, 7, color)
        rect(mod_x + 1, mod_y + 1, 5, 5, QR_FIXED_BG)
        rect(mod_x + 2, mod_y + 2, 3, 3, color)

def _paste_logo_with_pad(img: Image.Image, logo_path: str, ratio: float,
                         pad_scale: float, pad_radius: int, pad_color: str) -> Image.Image:
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except Exception:
        return img
    side = min(img.size)
    target = max(1, int(side * ratio))
    logo = logo.copy(); logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size

    if pad_scale and pad_scale != 1.0:
        pad_w = max(1, int(lw * pad_scale))
        pad_h = max(1, int(lh * pad_scale))
        pad = Image.new("RGBA", (pad_w, pad_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(pad)
        d.rounded_rectangle([0, 0, pad_w-1, pad_h-1], radius=pad_radius, fill=pad_color)
        cx = (img.width - pad_w) // 2
        cy = (img.height - pad_h) // 2
        img = img.copy()
        img.paste(pad, (cx, cy), pad)
        lx = cx + (pad_w - lw) // 2
        ly = cy + (pad_h - lh) // 2
    else:
        lx = (img.width - lw) // 2
        ly = (img.height - lh) // 2
    img.paste(logo, (lx, ly), logo)
    return img

def build_png_fixed_with_logo_and_finders(data: str) -> bytes:
    img, box, modules, offset = _compute_box_and_modules(data, QR_FIXED_BORDER)
    _recolor_finders_precise(img, box, QR_FIXED_BORDER, modules, QR_FIXED_FINDER, QR_FIXED_BG, offset=offset)
    img = _paste_logo_with_pad(img, QR_FIXED_LOGO_PATH, QR_FIXED_LOGO_RATIO,
                               pad_scale=QR_FIXED_LOGO_PAD, pad_radius=QR_FIXED_LOGO_PAD_RADIUS,
                               pad_color=QR_FIXED_BG)
    out = BytesIO()
    img.convert("RGB").save(out, format="PNG")
    return out.getvalue()
