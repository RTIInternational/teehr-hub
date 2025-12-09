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

# Install Python dependencies (excluding geospatial packages first)
RUN pip install --no-cache-dir \
    fastapi>=0.110.0 \
    uvicorn[standard]>=0.27.0 \
    gunicorn>=21.2.0 \
    trino>=0.327.0 \
    sqlalchemy>=2.0.25 \
    pandas>=2.2.0 \
    "numpy>=1.26.0,<2.0.0" \
    httpx>=0.26.0 \
    python-multipart>=0.0.7 \
    python-dotenv>=1.0.0 \
    orjson>=3.9.15

# Install geospatial packages (set GDAL config for ARM64 builds)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then \
        export GDAL_CONFIG=/usr/bin/gdal-config; \
    fi && \
    pip install --no-cache-dir \
    shapely==2.0.2 \
    pyproj==3.6.1 \
    fiona>=1.9.6 \
    "geopandas>=1.0.0,<2.0.0"

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
CMD ["gunicorn", "src.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
