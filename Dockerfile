# Build stage
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-install-project

# Production stage
FROM python:3.12-slim AS runtime

# Install system dependencies
# - libmupdf-dev: for PyMuPDF
# - libfreetype6, libjpeg, libpng, libtiff, zlib1g: for PDF rendering
# - tesseract-ocr: for OCR fallback in pymupdf4llm
# - ca-certificates: for HTTPS requests to NVIDIA/Tavily/Firecrawl APIs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    libfreetype6 \
    libjpeg62-turbo \
    libpng16-16 \
    libtiff6 \
    zlib1g \
    tesseract-ocr \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY --chown=appuser:appuser src/ ./
COPY --chown=appuser:appuser alembic/ ./alembic/
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Create data directories with correct permissions
RUN mkdir -p /app/data/uploads /app/data/outputs && chown -R appuser:appuser /app/data

# Switch to non-root user
USER appuser

# Set PATH to use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Environment variables (no defaults for secrets)
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]