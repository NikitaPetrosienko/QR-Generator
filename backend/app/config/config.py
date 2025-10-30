import json, os
from pathlib import Path
from typing import Dict, Any

# по умолчанию рядом с этим файлом: backend/app/config/qr_config.json
DEFAULT_CONFIG_PATH = (Path(__file__).resolve().parent / "qr_config.json").as_posix()

def load_all_config() -> Dict[str, Any]:

    # Читаем JSON КАЖДЫЙ запрос. Если файл битый/нет — {}.
    # Путь можно переопределить ENV переменной QR_CONFIG_FILE (относительный или абсолютный).
    env_path = os.getenv("QR_CONFIG_FILE")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            # если задали относительный путь — считаем от текущего рабочего каталога
            p = (Path.cwd() / env_path).resolve()
    else:
        p = Path(DEFAULT_CONFIG_PATH)

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data or {}
    except Exception:
        return {}
