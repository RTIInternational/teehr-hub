apiVersion: v1
kind: ConfigMap
metadata:
  name: xpublish-api-config
  labels:
    app: xpublish-api
    component: backend
data:
  # Remote/prod deployment — uses AWS S3 with IRSA or standard AWS_* env vars.
  ICECHUNK_REPOS: "ua-swann-4km,nwm30-forcing-analysis-assim"
  ICECHUNK_BUCKET: "${var.icechunk.bucket}"
  ICECHUNK_PREFIX: "${var.icechunk.prefix}"
  ICECHUNK_BRANCH: "main"
  ICECHUNK_STORAGE_MODE: "remote"
  # Not used in remote mode; kept so deployment.yaml.tpl key reference is valid.
  ICECHUNK_ENDPOINT_URL: ""
  AWS_DEFAULT_REGION: "us-east-2"
  CORS_ORIGINS: "${var.allowedOrigins}"
  KEYCLOAK_ISSUER_URL: "https://auth.${var.hostname}/realms/teehr"
  # Internal cluster URL avoids routing JWKS fetches through the ingress
  KEYCLOAK_JWKS_URL: "http://keycloak-service:8080/realms/teehr/protocol/openid-connect/certs"
  KEYCLOAK_ALLOWED_AUDIENCES: "teehr-api,teehr-frontend"
