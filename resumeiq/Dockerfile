# ResumeIQ - Full-stack production image for Google Cloud Run
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

ENV PORT=8080
EXPOSE 8080

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

CMD exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 90 app:app
