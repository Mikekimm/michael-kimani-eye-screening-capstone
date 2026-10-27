# Backend API image (deployment only; local development uses the .venv and SQLite).
# Build context is the repository root:  docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt "psycopg[binary]==3.2.3"

COPY backend/ backend/
COPY models/ models/
COPY scripts/seed.py scripts/seed.py

RUN useradd --create-home appuser && mkdir -p /app/data/uploads && chown -R appuser /app/data
USER appuser

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

# Apply migrations, create the demo accounts when SEED_* variables are set (safe to repeat), then serve on
# $PORT (set by hosting platforms such as Render; 8000 otherwise). The schema is never auto-created by the app.
CMD ["sh", "-c", "alembic upgrade head && if [ -n \"$SEED_ADMIN_EMAIL\" ]; then python /app/scripts/seed.py || echo \"seed skipped: set all six SEED_* variables\"; fi && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
