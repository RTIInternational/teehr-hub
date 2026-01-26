# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install geospatial dependencies for ARM64
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then \
        echo "Installing ARM64 geospatial packages..." && \
        apt-get update && \
        apt-get install -y gdal-bin libgdal-dev proj-bin libproj-dev libspatialindex-dev && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# Copy pyproject.toml first for dependency installation
COPY pyproject.toml ./

# Install dependencies from pyproject.toml
# Set GDAL config for ARM64 geospatial builds
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then \
        export GDAL_CONFIG=/usr/bin/gdal-config; \
    fi && \
    pip install --no-cache-dir .

# Copy application code
COPY src/ ./src/

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application (production by default)
# Increase timeout to 300 seconds (5 minutes) for long-running queries
CMD ["gunicorn", "src.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "300", "--graceful-timeout", "310", "--keep-alive", "30"]
