# backend/app/core/renderer.py
from io import BytesIO
from typing import Tuple, Optional

from PIL import Image, ImageDraw
import qrcode
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_Q

from backend.app.core.style import QRStyle


def _generate_qr_image_fixed(
    data: str,
    *,
    size_px: int,
    border_px: int,
    ec: str,
    fill: str,
    bg: str,
) -> Tuple[Image.Image, int, int, Tuple[int, int]]:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H if ec == "H" else ERROR_CORRECT_Q,
        box_size=1,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)

    modules = qr.modules_count
    qr_area = size_px - 2 * border_px
    box_size = qr_area / modules

    qr_img = qr.make_image(fill_color=fill, back_color=bg).convert("RGBA")
    target = int(modules * box_size)
    qr_img = qr_img.resize((target, target), Image.NEAREST)

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
    *,
    # Источник логотипа: либо путь к файлу, либо уже открытая картинка (RGBA/RGB).
    logo_path: Optional[str] = None,
    logo_image: Optional[Image.Image] = None,
    # Параметры размещения
    ratio: float,
    pad_scale: float,
    pad_radius: int,
    pad_color,  # может быть "#FFFFFF" или кортеж RGBA
) -> Image.Image:
    """
    Вставляет логотип по центру с опциональной подложкой.
    - Если передан logo_image — используем его.
    - Иначе пробуем открыть из logo_path.
    """
    try:
        if logo_image is None:
            if not logo_path:
                return img
            logo = Image.open(logo_path).convert("RGBA")
        else:
            # Защитимся от несовместимого режима
            logo = logo_image.convert("RGBA")
    except Exception:
        return img

    side = min(img.size)
    target = max(1, int(side * ratio))
    logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size

    # Подложка
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


def render_qr_png(
    data: str,
    style: QRStyle,
    *,
    # Если передан логотип из запроса (multipart) — используем его
    # с фиксированными параметрами «как в онлайн-сервисах».
    logo_image: Optional[Image.Image] = None,
) -> bytes:
    """
    Генерирует PNG QR-кода:
    - Всегда рисует ключевые квадраты (finder) цветом style.finder.
    - Если передан logo_image (путь НЕ используется) — вставляем его с:
        ratio=0.22, pad_scale=1.3, pad_radius=12, pad_color белый.
    - Иначе, если в стиле есть logo_path и ratio>0 — используем параметры из стиля.
    """
    canvas, box, modules, offset = _generate_qr_image_fixed(
        data=data,
        size_px=style.size,
        border_px=style.border,
        ec=style.ec,
        fill=style.fill,
        bg=style.bg,
    )

    _recolor_finders_precise(
        canvas, box=box, modules=modules, color=style.finder, bg=style.bg, offset=offset
    )

    if logo_image is not None:
        # Пользовательская загрузка: фиксированные «безопасные» параметры
        canvas = _paste_logo_with_pad(
            canvas,
            logo_image=logo_image,
            ratio=0.22,           # ~22% от стороны QR
            pad_scale=1.3,        # белая подложка чуть больше логотипа
            pad_radius=12,        # скругление как в популярных генераторах
            pad_color=(255, 255, 255, 255),  # белая подложка (всегда белая)
        )
    elif style.logo_path and style.logo_ratio > 0:
        # Корпоративный логотип из конфига (LK-режим)
        canvas = _paste_logo_with_pad(
            canvas,
            logo_path=style.logo_path,
            ratio=style.logo_ratio,
            pad_scale=style.logo_pad,
            pad_radius=style.logo_pad_radius,
            pad_color=style.bg,  # для LK используем цвет фона из стиля
        )

    out = BytesIO()
    canvas.convert("RGB").save(out, format="PNG")
    return out.getvalue()
