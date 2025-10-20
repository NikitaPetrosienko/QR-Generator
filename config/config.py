import json     
import os        

CONFIG_PATH = os.getenv("QR_CONFIG_FILE", "config.json")

def load_all_config() -> dict:
    """
    Каждый раз перечитываем JSON и возвращаем словарь параметров.
    Если файл отсутствует или битый - возвращаем пустой словарь {}.
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
