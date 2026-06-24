apiVersion: apps/v1
kind: Deployment
metadata:
  name: teehr-api
  labels:
    app: teehr-api
    component: backend
spec:
  replicas: ${environment.name == 'local' ? 1 : 1}
  selector:
    matchLabels:
      app: teehr-api
  template:
    metadata:
      labels:
        app: teehr-api
        component: backend
    spec:
      # nodeSelector:
      #   fved/nodegroup-name: core-a
      containers:
      - name: teehr-api
        image: ${actions.build.teehr-api.outputs.deploymentImageId}
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: TRINO_HOST
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: TRINO_HOST
        - name: TRINO_PORT
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: TRINO_PORT
        - name: TRINO_USER
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: TRINO_USER
        - name: TRINO_CATALOG
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: TRINO_CATALOG
        - name: TRINO_SCHEMA
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: TRINO_SCHEMA
        - name: CORS_ORIGINS
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: CORS_ORIGINS
        - name: KEYCLOAK_ISSUER_URL
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: KEYCLOAK_ISSUER_URL
        - name: KEYCLOAK_JWKS_URL
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: KEYCLOAK_JWKS_URL
        - name: KEYCLOAK_AUDIENCE
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: KEYCLOAK_AUDIENCE
        - name: KEYCLOAK_ALLOWED_AUDIENCES
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: KEYCLOAK_ALLOWED_AUDIENCES
        - name: API_KEYS_DB_HOST
          value: keycloak-pg
        - name: API_KEYS_DB_PORT
          value: "5432"
        - name: API_KEYS_DB_NAME
          valueFrom:
            secretKeyRef:
              name: keycloak-db-secrets
              key: database
        - name: API_KEYS_DB_USER
          valueFrom:
            secretKeyRef:
              name: keycloak-db-secrets
              key: username
        - name: API_KEYS_DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: keycloak-db-secrets
              key: password
        - name: API_KEYS_DB_DSN
          value: "postgresql://$(API_KEYS_DB_USER):$(API_KEYS_DB_PASSWORD)@$(API_KEYS_DB_HOST):$(API_KEYS_DB_PORT)/$(API_KEYS_DB_NAME)"
        - name: ANON_RATE_LIMIT_RPM
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: ANON_RATE_LIMIT_RPM
        - name: AUTH_RATE_LIMIT_RPM
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: AUTH_RATE_LIMIT_RPM
        - name: ROW_LIMIT_ANON
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: ROW_LIMIT_ANON
        - name: ROW_LIMIT_API_KEY
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: ROW_LIMIT_API_KEY
        - name: ROW_LIMIT_BASIC_USER
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: ROW_LIMIT_BASIC_USER
        - name: ROW_LIMIT_AUTH
          valueFrom:
            configMapKeyRef:
              name: teehr-api-config
              key: ROW_LIMIT_AUTH
        - name: API_KEY_HASH_SALT
          valueFrom:
            secretKeyRef:
              name: keycloak-secrets
              key: api-key-hash-salt
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          successThreshold: 1
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          successThreshold: 1
          failureThreshold: 3
        resources:
          requests:
            cpu: 1
            memory: "${environment.name == 'local' ? '1Gi' : '4Gi'}"
          limits:
            cpu: 2
            memory: 8Gi