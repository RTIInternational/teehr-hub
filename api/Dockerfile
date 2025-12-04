# Use Python 3.11 slim image as base
FROM python:3.11-slim

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

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies (excluding geospatial packages first)
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    trino==0.327.0 \
    sqlalchemy==2.0.23 \
    pandas==2.1.3 \
    numpy==1.25.2 \
    httpx==0.25.2 \
    python-multipart==0.0.6 \
    python-dotenv==1.0.0 \
    orjson==3.9.10

# Install geospatial packages (set GDAL config for ARM64 builds)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then \
        export GDAL_CONFIG=/usr/bin/gdal-config; \
    fi && \
    pip install --no-cache-dir \
    shapely==2.0.2 \
    pyproj==3.6.1 \
    fiona>=1.9.6 \
    geopandas==0.14.1

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

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
