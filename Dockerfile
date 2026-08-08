# ── SwingEdge Pro v3 — Production Image ─────────────────────────────────────
# Multi-stage build: Python 3.11-slim base, installs deps, copies app, runs uvicorn.

FROM python:3.11-slim AS base

# System deps for lxml, pandas, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Healthcheck — hit the /api/health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run uvicorn — bind 0.0.0.0:8000, no reload in production
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
