apiVersion: apps/v1
kind: Deployment
metadata:
  name: xpublish-api
  labels:
    app: xpublish-api
    component: backend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: xpublish-api
  template:
    metadata:
      labels:
        app: xpublish-api
        component: backend
    spec:
      containers:
      - name: xpublish-api
        image: ${actions.build.xpublish-api.outputs.deploymentImageId}
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: ICECHUNK_REPOS
          valueFrom:
            configMapKeyRef:
              name: xpublish-api-config
              key: ICECHUNK_REPOS
        - name: ICECHUNK_BRANCH
          valueFrom:
            configMapKeyRef:
              name: xpublish-api-config
              key: ICECHUNK_BRANCH
        - name: ICECHUNK_STORAGE_MODE
          valueFrom:
            configMapKeyRef:
              name: xpublish-api-config
              key: ICECHUNK_STORAGE_MODE
        - name: ICECHUNK_ENDPOINT_URL
          valueFrom:
            configMapKeyRef:
              name: xpublish-api-config
              key: ICECHUNK_ENDPOINT_URL
        - name: AWS_DEFAULT_REGION
          valueFrom:
            configMapKeyRef:
              name: xpublish-api-config
              key: AWS_DEFAULT_REGION
        - name: CORS_ORIGINS
          valueFrom:
            configMapKeyRef:
              name: xpublish-api-config
              key: CORS_ORIGINS
        - name: KEYCLOAK_ISSUER_URL
          valueFrom:
            configMapKeyRef:
              name: xpublish-api-config
              key: KEYCLOAK_ISSUER_URL
        - name: KEYCLOAK_JWKS_URL
          valueFrom:
            configMapKeyRef:
              name: xpublish-api-config
              key: KEYCLOAK_JWKS_URL
        - name: KEYCLOAK_ALLOWED_AUDIENCES
          valueFrom:
            configMapKeyRef:
              name: xpublish-api-config
              key: KEYCLOAK_ALLOWED_AUDIENCES
        # Minio credentials for local/kind — same secret used cluster-wide.
        # Remote/prod: omitted; use IRSA to grant S3 access via service account.
        ${if environment.name == "local"}
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: minio-secrets
              key: accesskey
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: minio-secrets
              key: secretkey
        ${endif}
        resources:
          requests:
            memory: "1Gi"
            cpu: "250m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          failureThreshold: 6
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
          failureThreshold: 3
