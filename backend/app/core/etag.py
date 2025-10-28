# backend/app/core/etag.py
import hashlib, os
from backend.app.core.style import QRStyle

def _file_hash(path: str) -> str:
    try:
        if not path or not os.path.exists(path):
            return "no-logo"
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "no-logo"

def style_signature(style: QRStyle) -> str:
    return "|".join([
        f"size={style.size}",
        f"border={style.border}",
        f"fill={style.fill}",
        f"bg={style.bg}",
        f"finder={style.finder}",
        f"ec={style.ec}",
        f"logo_hash={_file_hash(style.logo_path)}",
    ])
