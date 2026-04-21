apiVersion: v1
kind: ConfigMap
metadata:
  name: teehr-api-config
  labels:
    app: teehr-api
    component: backend
data:
  TRINO_HOST: "trino"
  TRINO_PORT: "8080"
  TRINO_USER: "teehr"
  TRINO_CATALOG: "iceberg"
  TRINO_SCHEMA: "teehr"
  CORS_ORIGINS: "${var.allowedOrigins}"