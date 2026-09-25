apiVersion: apps/v1
kind: Deployment
metadata:
  name: teehr-frontend
  labels:
    app: teehr-frontend
    version: production
spec:
  replicas: 2
  selector:
    matchLabels:
      app: teehr-frontend
  template:
    metadata:
      labels:
        app: teehr-frontend
        version: production
    spec:
      # nodeSelector:
      #   teehr-hub/nodegroup-name: core-a
      containers:
      - name: frontend
        image: ${actions.build.teehr-frontend-prod.outputs.deployment-image-id}
        ports:
        - containerPort: 8080
        # nginx serving a static bundle: CPU p95 and peak were both ~0 cores
        # over 47h (2026-09), memory peak 0.01Gi across both replicas. The
        # limit is left alone so a burst of requests can still be absorbed.
        resources:
          requests:
            memory: "64Mi"
            cpu: "25m"
          limits:
            memory: "256Mi"
            cpu: "200m"
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 3
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10