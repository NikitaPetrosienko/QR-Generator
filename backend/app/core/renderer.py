from io import BytesIO
from typing import Tuple, Optional

from PIL import Image, ImageDraw
import qrcode
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_Q

from backend.app.core.style import QRStyle


# ====== QR базовая генерация ======

def _generate_qr_image_fixed(
    data: str,
    *,
    size_px: int,
    border_px: int,
    ec: str,
    fill: str,
    bg: str,
) -> Tuple[Image.Image, int, int, Tuple[int, int]]:
    """
    Возвращает:
      - canvas (RGBA) размером size_px x size_px
      - int(box)       — «черновой» размер модуля (может отличаться от фактического)
      - modules        — число модулей по стороне
      - (offx, offy)   — смещение QR в канвасе (равно border_px)
    """
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
    box_size = qr_area / modules  # теоретический размер модуля

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
    actual_box = total_size / modules  # фактический (float) размер модуля

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


# ====== НОРМАЛИЗАЦИЯ ЛОГОТИПОВ (для загруженных пользователем) ======

def _autocrop_logo(img: Image.Image) -> Image.Image:
    """
    1) Обрезка прозрачных полей по альфе (>8)
    2) Мягкая обрезка «почти белых» полей, если альфа сплошная (RGB>=245, рамка >=3%)
    """
    im = img.convert("RGBA")
    w, h = im.size

    # --- 1) прозрачные поля ---
    a = im.getchannel("A")
    # бинариазуем альфу: всё, что > 8 — считаем «контент»
    mask = a.point(lambda p: 255 if p > 8 else 0)
    bbox = mask.getbbox()
    if bbox:
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        # fail-safe: не кропаем до крошек
        if bw >= 40 and bh >= 40:
            im = im.crop(bbox)
            w, h = im.size
            a = im.getchannel("A")

    # --- 2) «почти белые» поля (если альфа сплошная) ---
    if a.getextrema() == (255, 255):
        rgb = im.convert("RGB")
        px = rgb.load()

        def is_row_white(y: int) -> bool:
            for x in range(w):
                r, g, b = px[x, y]
                if not (r >= 245 and g >= 245 and b >= 245):
                    return False
            return True

        def is_col_white(x: int) -> bool:
            for y in range(h):
                r, g, b = px[x, y]
                if not (r >= 245 and g >= 245 and b >= 245):
                    return False
            return True

        # считаем толщину белой рамки по 4 сторонам
        top = 0
        while top < h and is_row_white(top):
            top += 1
        bottom = 0
        while bottom < h and is_row_white(h - 1 - bottom):
            bottom += 1
        left = 0
        while left < w and is_col_white(left):
            left += 1
        right = 0
        while right < w and is_col_white(w - 1 - right):
            right += 1

        min_side = min(w, h)
        thr = int(round(min_side * 0.03))  # >=3% стороны
        if min(top, bottom, left, right) >= thr:
            # однородность рамки (+/- 2px)
            if max(top, bottom, left, right) - min(top, bottom, left, right) <= 2:
                # кропаем по минимальной толщине
                t = min(top, bottom, left, right)
                # fail-safe: не уходим в ноль
                if w - (left + right) >= 40 and h - (top + bottom) >= 40:
                    im = im.crop((t, t, w - t, h - t))

    return im


def _paste_user_logo_normalized(
    img: Image.Image,
    *,
    logo_image: Image.Image,
    modules: int,
    module_px: float,
    data_side: int,
    max_center_cover: float = 0.20,   # максимум 20% площади квадрата данных
    base_ratio: float = 0.22,         # доля длинной стороны логотипа от data_side
    thin_ar_threshold: float = 2.5,   # если AR >= 2.5 — считаем «саблей»
    thin_ratio: float = 0.18,         # для «сабель» уменьшаем базовый таргет
    hard_ratio_cap: float = 0.26,     # жёстный потолок доли
    pad_modules: float = 1.5,         # толщина подложки в модулях
    pad_radius_modules: float = 2.0,  # радиус скругления в модулях
    pad_color=(255, 255, 255, 255),
) -> Image.Image:
    """
    Вставляет пользовательский логотип с:
      - автокропом,
      - масштабом по длинной стороне,
      - белой подложкой толщиной в МОДУЛЯХ QR,
      - ограничением покрытия центра (без внешнего бордера).
    """
    # --- 0) подготовка лого ---
    logo = _autocrop_logo(logo_image).convert("RGBA")
    lw0, lh0 = logo.size
    if lw0 <= 0 or lh0 <= 0:
        return img

    # --- 1) выбираем базовый таргет по AR ---
    ar = max(lw0, lh0) / max(1, min(lw0, lh0))
    ratio = thin_ratio if ar >= thin_ar_threshold else base_ratio
    ratio = min(ratio, hard_ratio_cap)

    # --- 2) первичный масштаб по длинной стороне ---
    # сторона внутреннего квадрата данных (без бордера)
    L = data_side * ratio
    if lw0 >= lh0:
        scale = L / lw0
    else:
        scale = L / lh0
    lw = max(1, int(round(lw0 * scale)))
    lh = max(1, int(round(lh0 * scale)))

    # --- 3) подложка фиксированной толщины в модулях ---
    pad_px = max(1, int(round(pad_modules * module_px)))
    radius_px = max(0, int(round(pad_radius_modules * module_px)))
    pad_w = lw + 2 * pad_px
    pad_h = lh + 2 * pad_px

    # --- 4) ограничение покрытия центра ---
    area_qr_data = float(data_side * data_side)
    cover = (pad_w * pad_h) / area_qr_data if area_qr_data > 0 else 0.0
    if cover > max_center_cover and cover > 0:
        # уменьшаем масштаб так, чтобы (pad_w * pad_h) == max_center_cover * area_qr_data
        k = (max_center_cover / cover) ** 0.5
        lw = max(1, int(round(lw * k)))
        lh = max(1, int(round(lh * k)))
        pad_w = lw + 2 * pad_px
        pad_h = lh + 2 * pad_px

    # дополнительный жёсткий лимит: не больше 26% длинной стороны
    if max(lw, lh) > int(data_side * hard_ratio_cap):
        k = (data_side * hard_ratio_cap) / max(1, max(lw, lh))
        lw = max(1, int(round(lw * k)))
        lh = max(1, int(round(lh * k)))
        pad_w = lw + 2 * pad_px
        pad_h = lh + 2 * pad_px

    # --- 5) рендер подложки и логотипа в центр ---
    # ограничим радиус с учётом размера
    radius_px = min(radius_px, pad_w // 2, pad_h // 2)

    # центрирование
    cx = (img.width - pad_w) // 2
    cy = (img.height - pad_h) // 2

    # подложка
    pad = Image.new("RGBA", (pad_w, pad_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(pad)
    d.rounded_rectangle([0, 0, pad_w - 1, pad_h - 1], radius=radius_px, fill=pad_color)
    img.paste(pad, (cx, cy), pad)

    # лого
    logo = logo.resize((lw, lh), Image.LANCZOS)
    lx = cx + (pad_w - lw) // 2
    ly = cy + (pad_h - lh) // 2
    img.paste(logo, (lx, ly), logo)
    return img


# ====== ВСТАВКА ЛОГО ИЗ КОНФИГА (LK) — старое поведение, без нормализации ======

def _paste_logo_with_pad_legacy(
    img: Image.Image,
    *,
    logo_path: Optional[str],
    ratio: float,
    pad_scale: float,
    pad_radius: int,
    pad_color,  # "#FFFFFF" либо RGBA
) -> Image.Image:
    try:
        if not logo_path:
            return img
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


# ====== ПУБЛИЧНАЯ ФУНКЦИЯ РЕНДЕРА ======

def render_qr_png(
    data: str,
    style: QRStyle,
    *,
    logo_image: Optional[Image.Image] = None,  # пользовательский логотип (multipart)
) -> bytes:
    """
    Генерирует PNG QR-кода:
      - рисует finder-углы цветом style.finder,
      - если задан logo_image — нормализует и вставляет с подложкой толщиной в «модулях»,
      - иначе при наличии style.logo_path — вставляет «как раньше» (LK-поведение из конфига).
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

    # Для вычислений в модулях берём фактический размер модуля (float)
    data_side = style.size - 2 * style.border
    module_px = data_side / float(modules) if modules > 0 else 1.0

    if logo_image is not None:
        # Пользовательский логотип — новая нормализация
        canvas = _paste_user_logo_normalized(
            canvas,
            logo_image=logo_image,
            modules=modules,
            module_px=module_px,
            data_side=data_side,
            max_center_cover=0.20,      # можно снизить до 0.15 при необходимости
            base_ratio=0.22,
            thin_ar_threshold=2.5,
            thin_ratio=0.18,
            hard_ratio_cap=0.26,
            pad_modules=1.5,
            pad_radius_modules=2.0,
            pad_color=(255, 255, 255, 255),  # белая подложка
        )
    elif style.logo_path and style.logo_ratio > 0:
        # Логотип из конфигурации (LK) — прежнее поведение
        canvas = _paste_logo_with_pad_legacy(
            canvas,
            logo_path=style.logo_path,
            ratio=style.logo_ratio,
            pad_scale=style.logo_pad,
            pad_radius=style.logo_pad_radius,
            pad_color=style.bg,
        )

    out = BytesIO()
    canvas.convert("RGB").save(out, format="PNG")
    return out.getvalue()
