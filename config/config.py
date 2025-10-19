# ===== Импорты =====
import json      # работа с JSON (чтение/запись)
import os        # работа с переменными окружения и файлами

# ===== Путь к конфигу =====
# Берём путь к файлу конфигурации:
# 1. Если задана переменная окружения QR_CONFIG_FILE → используем её.
# 2. Если нет → берём config.json по умолчанию.
CONFIG_PATH = os.getenv("QR_CONFIG_FILE", "config.json")


def load_all_config() -> dict:
    """
    Каждый раз перечитываем JSON и возвращаем словарь параметров.
    Если файл отсутствует или битый → возвращаем пустой словарь {}.
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
