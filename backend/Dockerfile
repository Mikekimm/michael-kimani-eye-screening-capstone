# Backend API image (deployment only; local development uses the .venv and SQLite).
# Build context is the repository root:  docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt "psycopg[binary]==3.2.3"

COPY backend/ backend/
COPY models/ models/

RUN useradd --create-home appuser && mkdir -p /app/data/uploads && chown -R appuser /app/data
USER appuser

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

# Apply migrations, then serve. The schema is never auto-created by the app.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
