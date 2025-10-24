from io import BytesIO
from typing import Dict, Tuple
import hashlib
import re
import unicodedata
import urllib.parse

from fastapi import Request, Response
from PIL import Image, ImageDraw
import qrcode
from qrcode.constants import ERROR_CORRECT_H

# =========================
# КОНСТАНТЫ (дефолты)
# =========================
FIXED_SIZE = 512
FIXED_BORDER = 8


# =========================
# ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ
# =========================
def _safe_ascii_filename(name: str, default: str = "qr_code") -> str:
    """Преобразуем имя файла в безопасное ASCII (убираем кириллицу и спецсимволы)."""
    base = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-")
    return base or default


def style_signature(cfg: Dict) -> str:
    """Детерминированная подпись стиля — для формирования ETag."""
    return "|".join([
        f"size={int(cfg.get('size', 512))}",
        f"border={int(cfg.get('border', 0))}",
        f"fill={str(cfg.get('fill', '#000000'))}",
        f"bg={str(cfg.get('bg', '#FFFFFF'))}",
        f"finder={str(cfg.get('finder', '#000000'))}",
        "ec=H",
    ])


def respond_fixed_png(
    request: Request,
    *,
    data_key: str,
    content: bytes,
    filename: str,
) -> Response:
    """
    Отправляем PNG с правильными заголовками:
    - ETag: для кеширования
    - Cache-Control: public, immutable (1 год)
    - Content-Disposition: inline (открыть в браузере)
    """
    etag = hashlib.sha256(data_key.encode("utf-8")).hexdigest()

    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)

    ascii_name = _safe_ascii_filename(filename) + ".png"
    utf8_name = urllib.parse.quote((filename or "qr_code") + ".png", safe="")

    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}',
    }

    return Response(content=content, media_type="image/png", headers=headers)


# =========================
# НИЗКОУРОВНЕВАЯ СБОРКА (фиксированный border)
# =========================
def _generate_qr_image_fixed(
    data: str,
    *,
    size_px: int,
    border_px: int,
    fill: str,
    bg: str,
) -> Tuple[Image.Image, int, int, Tuple[int, int]]:
    """
    Генерирует QR строго фиксированного размера и бордера.
    Без «встроенных» модульных бордеров, всё подчинено size_px и border_px.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=1,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)

    modules = qr.modules_count
    qr_area = size_px - 2 * border_px           # фактическая площадь под QR
    box_size = qr_area / modules                # сколько пикселей на один модуль

    # Рендерим QR и рескейлим точно под целевой размер (без внутренних бордеров)
    qr_img = qr.make_image(fill_color=fill, back_color=bg).convert("RGBA")
    target_size = int(modules * box_size)
    qr_img = qr_img.resize((target_size, target_size), Image.NEAREST)

    # Вклеиваем QR в канвас, строго с отступом border_px
    canvas = Image.new("RGBA", (size_px, size_px), bg)
    canvas.paste(qr_img, (border_px, border_px))

    return canvas, int(box_size), modules, (border_px, border_px)


def _recolor_finders_precise(
    img: Image.Image,
    *,
    box: int,
    modules: int,
    color: str,
    bg: str,
    offset: Tuple[int, int],
):
    """
    Точно перекрашиваем три finder-паттерна после рендера.
    Расчёт идёт в пикселях по фактическому масштабу.
    """
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


# =========================
# ПУБЛИЧНАЯ ФУНКЦИЯ
# =========================
def build_png_fixed_with_logo_and_finders(
    data: str,
    *,
    size: int = FIXED_SIZE,
    border: int = FIXED_BORDER,
    fill: str = "#000000",
    bg: str = "#FFFFFF",
    finder: str = "#000000",
) -> bytes:
    """
    Генерация PNG-изображения QR.
    Параметры передаются явно из эндпойнтов.
    """

    # Валидация параметров
    size = max(128, min(int(size), 2048))
    border = max(0, min(int(border), size // 4))

    # Генерация QR с точным border
    canvas, box, modules, offset = _generate_qr_image_fixed(
        data=data,
        size_px=size,
        border_px=border,
        fill=fill,
        bg=bg,
    )

    # Перекраска finder-паттернов
    _recolor_finders_precise(
        canvas,
        box=box,
        modules=modules,
        color=finder,
        bg=bg,
        offset=offset,
    )

    out = BytesIO()
    canvas.convert("RGB").save(out, format="PNG")
    return out.getvalue()
