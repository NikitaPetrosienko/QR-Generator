FROM python:3.11.5-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Moscow \
    PYTHONPATH=/app
WORKDIR /app
RUN useradd -m -u 10001 appuser
COPY --chown=appuser:appuser . /app
RUN set -eux; \
    python -m pip install --no-index --find-links=/app/pkgs -r requirements.txt --no-build-isolation; \
    mkdir -p /app/logs; \
    rm -rf /root/.cache/pip /app/pkgs
EXPOSE 8000
USER appuser
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "2", "-b", "0.0.0.0:8000", "main:app", "--access-logfile", "-", "--error-logfile", "-"]
