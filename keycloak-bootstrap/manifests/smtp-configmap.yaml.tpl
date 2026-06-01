apiVersion: v1
kind: ConfigMap
metadata:
  name: keycloak-smtp-config
  labels:
    app: keycloak-bootstrap
data:
  smtp-host: "${var.smtp.host}"
  smtp-port: "${var.smtp.port}"
  smtp-from-display-name: "${var.smtp.fromDisplayName}"
  smtp-reply-to-display-name: "${var.smtp.replyToDisplayName}"
  smtp-starttls: "${var.smtp.starttls}"
  smtp-ssl: "${var.smtp.ssl}"
