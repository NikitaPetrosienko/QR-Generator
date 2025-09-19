# Базовый образ с Python
FROM python:3.11-slim

# Чтобы питон писал логи сразу в stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Рабочая директория в контейнере
WORKDIR /app

# Сначала ставим зависимости
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Потом копируем исходники
COPY . /app

# Открываем порт 8000
EXPOSE 8000

# Запускаем uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
