# Digest-pinned for fully reproducible builds; Dependabot (docker ecosystem)
# opens PRs to bump this when the upstream image updates
FROM python:3.11.15-slim-trixie@sha256:f9fa7f851e38bfb19c9de3afbc4b86ae7176ea7aaf94535c31df5458d5849457

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