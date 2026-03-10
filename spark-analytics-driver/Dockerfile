# Spark Analytics Driver Dockerfile
# Uses the teehr-prefect image as base (already has teehr + Java + PySpark + Trino)

ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Copy the analytics driver package
WORKDIR /app
COPY spark_analytics_driver/ ./spark_analytics_driver/
COPY pyproject.toml ./

# Install the driver package
RUN pip install --no-cache-dir -e .

# Set default command
CMD ["python", "-m", "spark_analytics_driver"]
