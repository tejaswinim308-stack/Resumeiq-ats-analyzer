# ResumeIQ backend - production image for Google Cloud Run
FROM python:3.12-slim

# Keep Python output unbuffered so logs show up immediately in Cloud Logging.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects PORT; default to 8080 for local `docker run`.
ENV PORT=8080
EXPOSE 8080

# Run as a non-root user.
RUN useradd --create-home appuser
USER appuser

# gunicorn binds 0.0.0.0:$PORT, matching Cloud Run's requirement.
CMD exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 90 app:app
