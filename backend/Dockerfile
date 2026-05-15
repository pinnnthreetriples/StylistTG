FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LOCAL_STORAGE_PATH=/var/lib/stylisttg/storage \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN addgroup --system stylisttg && \
    adduser --system --ingroup stylisttg stylisttg && \
    mkdir -p /var/lib/stylisttg/storage /var/lib/stylisttg/logs && \
    chown -R stylisttg:stylisttg /var/lib/stylisttg

COPY backend/pyproject.toml backend/uv.lock backend/alembic.ini ./
COPY backend/app ./app
COPY backend/migrations ./migrations

RUN python -m pip install --upgrade pip && \
    python -m pip install uv==0.10.9 && \
    uv sync --locked --no-dev && \
    /usr/local/bin/python -m pip uninstall -y uv

USER stylisttg

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
