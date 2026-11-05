# Read-only UI preview, not a video-processing worker.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GENJUSTSU_HOSTED=1 \
    GENJUSTSU_DEMO=1

WORKDIR /app
RUN python -m pip install --no-cache-dir \
        fastapi==0.142.2 \
        uvicorn==0.54.0 \
        python-multipart==0.0.32 \
    && groupadd --system genjustsu \
    && useradd --system --gid genjustsu --home-dir /app genjustsu \
    && mkdir /app/runs \
    && chown genjustsu:genjustsu /app/runs

# Deliberately exclude processing code, saved jobs and local configuration.
COPY app.py ./app.py
COPY static/ ./static/

USER genjustsu
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
