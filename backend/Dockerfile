# Digest-pinned for fully reproducible builds; Dependabot (docker ecosystem)
# opens PRs to bump this when the upstream image updates
FROM python:3.14.0-slim-trixie@sha256:0aecac02dc3d4c5dbb024b753af084cafe41f5416e02193f1ce345d671ec966e

WORKDIR /app

# Install only necessary system deps and uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir uv==0.11.21

# Copy project files for dependency installation
COPY backend/pyproject.toml .
COPY backend/uv.lock* .

# Install locked dependencies using uv (system-wide); uv.lock is the source of truth
RUN uv export --frozen --no-dev --no-emit-project -o requirements.txt && \
    uv pip sync --system requirements.txt

# Copy application code
COPY backend/app/ ./app/

# Backend doesn't need the codebook file - it receives it via API

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]