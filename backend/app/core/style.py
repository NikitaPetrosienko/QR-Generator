from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, field_validator, model_validator
import os, re

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class QRStyle(BaseModel):
    size: int = 512
    border: int = 6
    fill: str = "#000000"
    bg: str = "#FFFFFF"
    finder: str = "#000000"
    ec: Literal["H", "Q"] = "H"

    # логотип (для ЛК)
    logo_path: Optional[str] = None
    logo_ratio: float = 0.0          # 0 — без логотипа
    logo_pad: float = 1.0
    logo_pad_radius: int = 0

    # --- Pydantic v2: field_validator / model_validator ---

    @field_validator("size", mode="before")
    @classmethod
    def _coerce_size(cls, v):
        try:
            v = int(v)
        except Exception:
            v = 512
        return max(128, min(v, 2048))

    @field_validator("border", mode="before")
    @classmethod
    def _coerce_border(cls, v):
        try:
            return int(v)
        except Exception:
            return 8

    @field_validator("fill", "bg", "finder", mode="before")
    @classmethod
    def _hex_color(cls, v, info):
        s = str(v or "").strip()
        if HEX_RE.match(s):
            return s
        # дефолт под конкретное поле
        defaults = {"fill": "#000000", "bg": "#FFFFFF", "finder": "#000000"}
        name = getattr(info, "field_name", "")  # v2: info.field_name
        return defaults.get(name, "#000000")

    @field_validator("ec", mode="before")
    @classmethod
    def _ec_upper(cls, v):
        s = str(v or "H").upper()
        return s if s in ("H", "Q") else "H"

    @model_validator(mode="after")
    def _fix_border_vs_size(self):
        # финальная подгонка border относительно size
        self.border = max(0, min(int(self.border), self.size // 4))
        return self

    # -------- helpers --------

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "QRStyle":
        """Поддерживает плоский формат конфигурации (QR_SIZE, QR_FILL, ...)."""
        return cls(
            size=cfg.get("QR_SIZE", 512),
            border=cfg.get("QR_BORDER_PX", cfg.get("QR_BORDER", 8)),
            fill=cfg.get("QR_FILL", "#000000"),
            bg=cfg.get("QR_BG", "#FFFFFF"),
            finder=cfg.get("QR_FINDER", "#000000"),
            ec=str(cfg.get("QR_EC", "H")).upper(),
            logo_path=cfg.get("QR_LOGO"),
            logo_ratio=float(cfg.get("QR_LOGO_RATIO", 0.0)),
            logo_pad=float(cfg.get("QR_LOGO_PAD", 1.0)),
            logo_pad_radius=int(cfg.get("QR_LOGO_PAD_RADIUS", 0)),
        )

    def merged(self, overrides: Optional[Dict[str, Any]] = None, *, allow_logo: bool = False) -> "QRStyle":
        """Смешиваем со словарём overrides от запроса. Лого — только если allow_logo=True."""
        if not overrides:
            return self
        d = self.model_dump()
        for k in ("size", "border", "fill", "bg", "finder", "ec"):
            if overrides.get(k) is not None:
                d[k] = overrides[k]
        if allow_logo:
            for k in ("logo_path", "logo_ratio", "logo_pad", "logo_pad_radius"):
                if overrides.get(k) is not None:
                    d[k] = overrides[k]
        else:
            d["logo_path"] = None
            d["logo_ratio"] = 0.0
        return QRStyle(**d)


def vcard_ext_base_from_env_or_cfg(cfg: Dict[str, Any], env_key: str = "VCARD_EXT_BASE", default: str = "+74957486424") -> str:
    return os.getenv(env_key, cfg.get("VCARD_EXT_BASE", default))
