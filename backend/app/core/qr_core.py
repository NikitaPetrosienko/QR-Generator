"""
qr_core.py — ядро генерации PNG QR-кода.
Без зависимостей от config.json и /assets: все стилевые параметры
передаются из эндпойнтов (или используются дефолты — Ч/Б).

Экспортируемые функции:
- build_png_fixed_with_logo_and_finders(data, *, size, border, fill, bg, finder) -> bytes
- respond_fixed_png(request, *, data_key, content, filename) -> fastapi.Response
- style_signature(style_dict) -> str
"""

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
        f"border={int(cfg.get('border', 8))}",
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

    # Если у клиента уже есть такой же ETag — отдать 304 Not Modified
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
# НИЗКОУРОВНЕВАЯ СБОРКА
# =========================

def _compute_canvas_and_metrics(
    data: str,
    *,
    size: int,
    border_px: int,
    fill: str,
    bg: str,
) -> Tuple[Image.Image, int, int, Tuple[int, int]]:
    """
    Генерируем QR без логотипа, раскладываем на канвас фиксированного размера.
    Возвращаем:
      - canvas (size x size)
      - фактический размер одного модуля (box)
      - число модулей в матрице QR (modules)
      - смещение (offset_x, offset_y), куда вклеен QR на канвас.
    """
    # 1) пробный QR без внешнего поля: узнаём число модулей
    probe = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=1,
        border=0,
    )
    probe.add_data(data)
    probe.make(fit=True)
    modules = probe.modules_count

    # 2) вычисляем размер модуля, чтобы уложиться в size с заданным pixel-бордером
    total_pixels_for_modules = size - 2 * border_px
    box = max(1, total_pixels_for_modules // modules)

    # 3) рендерим основной QR с нулевым border (он нам не нужен, мы сами рисуем поля)
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=box,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=fill, back_color=bg).convert("RGBA")

    # 4) создаём канвас точно size x size и центрируем QR внутри с pixel-бордером
    canvas = Image.new("RGBA", (size, size), bg)
    off_x = (size - qr_img.size[0]) // 2
    off_y = (size - qr_img.size[1]) // 2
    # гарантируем не меньше заданного border_px
    off_x = max(off_x, border_px)
    off_y = max(off_y, border_px)

    canvas.paste(qr_img, (off_x, off_y))
    return canvas, box, modules, (off_x, off_y)


def _recolor_finders_precise(
    img: Image.Image,
    *,
    box: int,
    modules: int,
    margin_px: int,
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

    # фактический модуль в пикселях (может не совпадать с идеальным делением)
    # ширина QR-матрицы в пикселях:
    qr_w = modules * box
    # если QR вклеен с отступами, рисуем относительно offx/offy
    actual_box = box

    def rect(mx, my, w, h, fill):
        x0 = offx + mx * actual_box
        y0 = offy + my * actual_box
        x1 = x0 + w * actual_box - 1
        y1 = y0 + h * actual_box - 1
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
    size: int = 512,
    border: int = 8,
    fill: str = "#000000",
    bg: str = "#FFFFFF",
    finder: str = "#000000",
) -> bytes:
    """
    Генерация PNG-изображения QR:
    """
    # ЖЁСТКО ПРИНИМАЕМ ТОЛЬКО ФИКСИРОВАННЫЕ ЗНАЧЕНИЯ
    size = FIXED_SIZE
    border = FIXED_BORDER

    canvas, box, modules, offset = _compute_canvas_and_metrics(
        data, size=size, border_px=border, fill=fill, bg=bg
    )
    _recolor_finders_precise(
        canvas, box=box, modules=modules, margin_px=border,
        color=finder, bg=bg, offset=offset
    )

    out = BytesIO()
    canvas.convert("RGB").save(out, format="PNG")
    return out.getvalue()
