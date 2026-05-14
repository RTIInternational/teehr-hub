apiVersion: batch/v1
kind: Job
metadata:
  name: keycloak-bootstrap
  labels:
    app: keycloak-bootstrap
spec:
  backoffLimit: 6
  template:
    metadata:
      labels:
        app: keycloak-bootstrap
    spec:
      restartPolicy: OnFailure
      containers:
        - name: keycloak-config-cli
          image: adorsys/keycloak-config-cli:latest-26@sha256:2d2a0663cf324379d9ffab896db8d00293cd0326151968b319cf166f6eec8fca
          env:
            - name: KEYCLOAK_URL
              value: http://keycloak-service:8080
            - name: KEYCLOAK_USER
              valueFrom:
                secretKeyRef:
                  name: keycloak-admin-secrets
                  key: username
            - name: KEYCLOAK_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: keycloak-admin-secrets
                  key: password
            - name: JUPYTERHUB_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: jupyterhub
                  key: OAUTH_CLIENT_SECRET
            - name: PREFECT_OAUTH2_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: prefect-oidc-secrets
                  key: client-secret
            - name: TEEHR_API_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: teehr-api-secrets
                  key: client-secret
            - name: SMTP_HOST
              value: "${var.smtp.host}"
            - name: SMTP_PORT
              value: "${var.smtp.port}"
            - name: SMTP_FROM
              valueFrom:
                secretKeyRef:
                  name: keycloak-secrets
                  key: smtp-from
            - name: SMTP_FROM_DISPLAY_NAME
              value: "${var.smtp.fromDisplayName}"
            - name: SMTP_REPLY_TO
              valueFrom:
                secretKeyRef:
                  name: keycloak-secrets
                  key: smtp-reply-to
            - name: SMTP_REPLY_TO_DISPLAY_NAME
              value: "${var.smtp.replyToDisplayName}"
            - name: SMTP_USERNAME
              valueFrom:
                secretKeyRef:
                  name: keycloak-secrets
                  key: smtp-username
            - name: SMTP_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: keycloak-secrets
                  key: smtp-password
            - name: SMTP_STARTTLS
              value: "${var.smtp.starttls}"
            - name: SMTP_SSL
              value: "${var.smtp.ssl}"
            - name: IMPORT_FILES_LOCATIONS
              value: /config/*
            - name: IMPORT_VARSUBSTITUTION_ENABLED
              value: "true"
            - name: KEYCLOAK_AVAILABILITYCHECK_ENABLED
              value: "true"
            - name: KEYCLOAK_AVAILABILITYCHECK_TIMEOUT
              value: "300s"
            - name: KEYCLOAK_SSLVERIFY
              value: "false"
            - name: IMPORT_CACHE_ENABLED
              value: "false"
          volumeMounts:
            - name: keycloak-bootstrap-config
              mountPath: /config
      volumes:
        - name: keycloak-bootstrap-config
          configMap:
            name: keycloak-realm-bootstrap
