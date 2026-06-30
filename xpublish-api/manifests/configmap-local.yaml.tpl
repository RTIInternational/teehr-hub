apiVersion: v1
kind: ConfigMap
metadata:
  name: xpublish-api-config
  labels:
    app: xpublish-api
    component: backend
data:
  # Local/kind deployment — uses minio as the S3-compatible store.
  # Bucket name matches the minio warehouse bucket used by the rest of the cluster.
  ICECHUNK_REPOS: "ua-swann-4km,nwm30-forcing-analysis-assim"
  ICECHUNK_BUCKET: "${var.icechunk.bucket}"
  ICECHUNK_PREFIX: "${var.icechunk.prefix}"
  ICECHUNK_BRANCH: "main"
  ICECHUNK_STORAGE_MODE: "local"
  # Matches the MINIO_SERVER value used cluster-wide (http://minio:9000)
  ICECHUNK_ENDPOINT_URL: "http://minio:9000"
  AWS_DEFAULT_REGION: "us-east-1"
  CORS_ORIGINS: "${var.allowedOrigins}"
  KEYCLOAK_ISSUER_URL: "https://auth.${var.hostname}/realms/teehr"
  # Internal cluster URL avoids routing JWKS fetches through the ingress
  KEYCLOAK_JWKS_URL: "http://keycloak-service:8080/realms/teehr/protocol/openid-connect/certs"
  KEYCLOAK_ALLOWED_AUDIENCES: "teehr-api,teehr-frontend"
