# ===== Импорты =====
import hashlib               # для подсчёта SHA256 (ETag и хэш логотипа)
import unicodedata           # для нормализации имени файла
import re                    # регулярки (чистка имён файлов и телефонов)
import urllib.parse          # кодирование имени файла в HTTP-заголовке
from io import BytesIO       # буфер для сохранения PNG в память
from typing import Tuple     # типизация

import qrcode
from qrcode.constants import ERROR_CORRECT_Q, ERROR_CORRECT_H
from PIL import Image, ImageDraw
from fastapi import Request, Response

from config.config import load_all_config   # читаем JSON при каждом запросе


# ==================== ХЕШ / СТИЛЬ ====================

def _file_hash(path: str) -> str:
    """SHA256 от файла (например, логотипа), чтобы кэш различал версии."""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "no-logo"


def style_signature(cfg: dict) -> str:
    """Подпись текущего стиля (для ETag)."""
    return "|".join([
        f"size={cfg.get('QR_SIZE', 256)}",
        f"border={cfg.get('QR_BORDER', 0)}",
        f"fill={cfg.get('QR_FILL', '#009639')}",
        f"bg={cfg.get('QR_BG', '#FFFFFF')}",
        f"finder={cfg.get('QR_FINDER', '#EAAA00')}",
        f"logo={cfg.get('QR_LOGO', 'assets/logo.png')}",
        f"logo_hash={_file_hash(cfg.get('QR_LOGO', 'assets/logo.png'))}",
        f"logo_ratio={cfg.get('QR_LOGO_RATIO', 0.5)}",
        f"logo_pad={cfg.get('QR_LOGO_PAD', 0.5)}",
        f"logo_pad_radius={cfg.get('QR_LOGO_PAD_RADIUS', 0)}",
        f"ec={'H' if str(cfg.get('QR_EC', 'H')).upper() == 'H' else 'Q'}",
    ])


# ==================== HTTP-ОТВЕТ ====================

def _safe_ascii_filename(name: str, default: str = "vcard_qr") -> str:
    """Делаем имя файла ASCII-safe (убираем кириллицу и спецсимволы)."""
    base = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-")
    return base or default


def respond_fixed_png(
    request: Request,
    *,
    data_key: str,
    content: bytes,
    filename: str
) -> Response:
    """
    Возвращаем PNG с заголовками:
    - ETag (для кеширования)
    - Cache-Control (immutable, хранится год)
    - Content-Disposition (inline → откроется в браузере)
    """
    etag = hashlib.sha256(data_key.encode("utf-8")).hexdigest()

    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)  # Not Modified

    ascii_name = _safe_ascii_filename(filename) + ".png"
    utf8_name = urllib.parse.quote((filename or "vcard_qr") + ".png", safe="")

    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}',
    }
    return Response(content=content, media_type="image/png", headers=headers)


# ==================== РЕНДЕР QR ====================

def _compute_box_and_modules(
    data: str,
    margin_modules: int,
    size: int,
    eclevel,
    fill: str,
    bg: str
) -> Tuple[Image.Image, int, int, Tuple[int, int]]:
    """
    Генерация QR-кода:
    - подгоняем под фиксированный размер
    - учитываем рамку и коррекцию ошибок
    """
    qr_tmp = qrcode.QRCode(
        version=None,
        error_correction=eclevel,
        box_size=1,
        border=0
    )
    qr_tmp.add_data(data)
    qr_tmp.make(fit=True)
    modules = qr_tmp.modules_count

    total_modules = modules + margin_modules * 2
    box_size = max(1, size // total_modules)

    qr = qrcode.QRCode(
        version=None,
        error_correction=eclevel,
        box_size=box_size,
        border=margin_modules
    )
    qr.add_data(data)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color=fill, back_color=bg).convert("RGBA")

    canvas = Image.new("RGBA", (size, size), bg)
    offset_x = (size - img_qr.size[0]) // 2
    offset_y = (size - img_qr.size[1]) // 2
    canvas.paste(img_qr, (offset_x, offset_y))

    return canvas, box_size, modules, (offset_x, offset_y)


def _recolor_finders_precise(
    img: Image.Image,
    box: int,
    margin: int,
    modules: int,
    color: str,
    bg: str,
    offset=(0, 0)
):
    """Перекрашиваем finder-паттерны (три угловых квадрата)."""
    draw = ImageDraw.Draw(img)
    offx, offy = offset

    def rect(mod_x, mod_y, w_mods, h_mods, fill):
        x0 = offx + (margin + mod_x) * box
        y0 = offy + (margin + mod_y) * box
        x1 = x0 + w_mods * box - 1
        y1 = y0 + h_mods * box - 1
        draw.rectangle([x0, y0, x1, y1], fill=fill)

    for mod_x, mod_y in [(0, 0), (modules - 7, 0), (0, modules - 7)]:
        rect(mod_x,     mod_y,     7, 7, color)
        rect(mod_x + 1, mod_y + 1, 5, 5, bg)
        rect(mod_x + 2, mod_y + 2, 3, 3, color)


def _paste_logo_with_pad(
    img: Image.Image,
    logo_path: str,
    ratio: float,
    pad_scale: float,
    pad_radius: int,
    pad_color: str
) -> Image.Image:
    """Вставляем логотип в центр с подложкой."""
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except Exception:
        return img

    side = min(img.size)
    target = max(1, int(side * ratio))
    logo = logo.copy()
    logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size

    if pad_scale and pad_scale != 1.0:
        pad_w = max(1, int(lw * pad_scale))
        pad_h = max(1, int(lh * pad_scale))
        pad = Image.new("RGBA", (pad_w, pad_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(pad)
        d.rounded_rectangle(
            [0, 0, pad_w - 1, pad_h - 1],
            radius=pad_radius,
            fill=pad_color
        )
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
    """
    Финальная сборка QR-кода.
    Каждый вызов перечитывает config.json и собирает QR по параметрам.
    """
    cfg = load_all_config()

    size = int(cfg.get("QR_SIZE", 256))
    border = int(cfg.get("QR_BORDER", 0))
    fill = str(cfg.get("QR_FILL", "#009639"))
    bg = str(cfg.get("QR_BG", "#FFFFFF"))
    finder = str(cfg.get("QR_FINDER", "#EAAA00"))
    logo_path = str(cfg.get("QR_LOGO", "assets/logo.png"))
    logo_ratio = float(cfg.get("QR_LOGO_RATIO", 0.5))
    logo_pad = float(cfg.get("QR_LOGO_PAD", 0.5))
    logo_pad_radius = int(cfg.get("QR_LOGO_PAD_RADIUS", 0))
    eclevel = (
        ERROR_CORRECT_H
        if str(cfg.get("QR_EC", "H")).upper() == "H"
        else ERROR_CORRECT_Q
    )

    img, box, modules, offset = _compute_box_and_modules(
        data,
        border,
        size,
        eclevel, # указываем именно так, по принципу DRY
        fill,
        bg,
    )
    _recolor_finders_precise(img, box, border, modules, finder, bg, offset=offset)
    img = _paste_logo_with_pad(img, logo_path, logo_ratio, logo_pad, logo_pad_radius, bg)

    out = BytesIO()
    img.convert("RGB").save(out, format="PNG")
    return out.getvalue()
