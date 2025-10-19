FROM python:3.11-slim AS base
# Базовый образ: минимальный Debian + Python 3.11.
# "slim" — облегчённый вариант (меньше размер, меньше пакетов по умолчанию).

# системные настройки
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Moscow
# PYTHONDONTWRITEBYTECODE=1 — не писать *.pyc (чуть меньше мусора в образе).
# PYTHONUNBUFFERED=1 — безбуферный stdout/stderr (логи сразу видны).
# PIP_NO_CACHE_DIR=1 — pip не кэширует колёса → меньше слой образа.
# TZ=Europe/Moscow — таймзона в контейнере (логам, времени и т.д.).

# ставим системные пакеты
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# apt-get update — обновили индексы пакетов.
# build-essential — компилятор/заголовки (нужны, если какие-то wheels собираются из исходников).
# curl — нужен для healthcheck (curl в контейнере вызывает /healthz).
# ca-certificates — корневые сертификаты (TLS).
# rm -rf /var/lib/apt/lists/* — чистим индексы apt → уменьшаем слой образа.

# непривилегированный пользователь
RUN useradd -m -u 10001 appuser
# Создаём пользователя appuser (uid 10001) с домашней директорией.
# Без root внутри — безопаснее.

WORKDIR /app
# Рабочая директория. Все последующие команды (и запуск) выполняются отсюда.

# зависимости
COPY requirements.txt .
# Копируем файл зависимостей.
RUN pip install --upgrade pip && pip install -r requirements.txt 
# Обновляем pip и ставим зависимости из requirements.txt.

# код и ресурсы
COPY backend ./backend
COPY frontend ./frontend 
COPY config ./config
COPY assets ./assets
COPY README.md ./
# Копируем исходники приложения и статические файлы внутрь образа.

# порт приложения 
EXPOSE 8000
# Мета-информация (какой порт слушает процесс внутри).
# Compose/Run будут ориентироваться на это при публикации портов.

# права доступа
RUN chown -R appuser:appuser /app
# Меняем владельца каталога /app на appuser, чтобы непривилегированный юзер мог читать/писать.
USER appuser
# Дальнейшие команды (и сам процесс приложения) будут запускаться от имени appuser (не root).

# запуск gunicorn с uvicorn
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "2", "-b", "0.0.0.0:8000", "backend.main:app", \
     "--access-logfile", "-", "--error-logfile", "-"]
# CMD — команда по умолчанию при запуске контейнера:
# gunicorn — WSGI/ASGI сервер.
# -k uvicorn.workers.UvicornWorker — используем рабочие процессы Uvicorn (ASGI) внутри Gunicorn.
# -w "2" — число воркеров = 2 (два независимых процесса обработки запросов).
# -b "0.0.0.0:8000" — слушать на всех интерфейсах, порт 8000 (совпадает с EXPOSE/ports).
# "app.main:app" — путь до ASGI-приложения: пакет app, модуль main, объект app.
# --access-logfile "-" — писать access-лог в stdout. логи и выводы системы, нужны или нет?
# --error-logfile "-" — писать error-лог в stderr.
