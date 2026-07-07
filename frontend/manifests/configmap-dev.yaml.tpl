apiVersion: v1
kind: ConfigMap
metadata:
  name: teehr-frontend-config
  labels:
    app: teehr-frontend
data:
  NODE_ENV: "development"
  VITE_API_BASE_URL: "https://api.${var.hostname}"
  VITE_KEYCLOAK_URL: "https://auth.${var.hostname}"
  VITE_PREFECT_URL: "https://prefect.${var.hostname}"
  VITE_JUPYTERHUB_URL: "https://hub.${var.hostname}/hub/spawn"
  VITE_KEYCLOAK_REALM: "teehr"
  VITE_KEYCLOAK_CLIENT_ID: "teehr-frontend"
  VITE_ALLOWED_HOSTS: "dashboards.${var.hostname}"