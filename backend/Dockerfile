FROM python:3.11-slim

WORKDIR /app

# Install only necessary system deps and uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir uv

# Copy project files for dependency installation
COPY backend/pyproject.toml .
COPY backend/uv.lock* .

# Compile and install dependencies using uv (system-wide)
RUN uv pip compile pyproject.toml -o requirements.txt && \
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