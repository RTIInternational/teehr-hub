apiVersion: v1
kind: ConfigMap
metadata:
  name: teehr-frontend-config
  labels:
    app: teehr-frontend
data:
  NODE_ENV: "development"
  VITE_API_BASE_URL: "https://api.${var.hostname}"
  VITE_ALLOWED_HOSTS: "dashboards.${var.hostname}"