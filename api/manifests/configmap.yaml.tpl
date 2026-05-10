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
  KEYCLOAK_ISSUER_URL: "https://auth.${var.hostname}/realms/teehr"
  KEYCLOAK_JWKS_URL: "http://keycloak-service:8080/realms/teehr/protocol/openid-connect/certs"
  KEYCLOAK_AUDIENCE: "teehr-api"
  KEYCLOAK_ALLOWED_AUDIENCES: "teehr-api,teehr-frontend"
  ANON_RATE_LIMIT_RPM: "20"
  AUTH_RATE_LIMIT_RPM: "120"
  ROW_LIMIT_ANON: "200"
  ROW_LIMIT_API_KEY: "50000"
  ROW_LIMIT_BASIC_USER: "50000"
  ROW_LIMIT_AUTH: "10000"