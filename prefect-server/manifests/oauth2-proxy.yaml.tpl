apiVersion: apps/v1
kind: Deployment
metadata:
  name: prefect-oauth2-proxy
  namespace: ${environment.namespace}
  labels:
    app: prefect-oauth2-proxy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prefect-oauth2-proxy
  template:
    metadata:
      labels:
        app: prefect-oauth2-proxy
    spec:
      containers:
      - name: oauth2-proxy
        image: quay.io/oauth2-proxy/oauth2-proxy:v7.7.1
        args:
          - --provider=oidc
          - --http-address=0.0.0.0:4180
          - --upstream=http://prefect-server:4200
          - --redirect-url=https://prefect.${var.hostname}/oauth2/callback
          - --oidc-issuer-url=http://keycloak-service:8080/realms/teehr
          - --skip-oidc-discovery=true
          - --insecure-oidc-skip-issuer-verification=true
          - --login-url=https://auth.${var.hostname}/realms/teehr/protocol/openid-connect/auth
          - --redeem-url=http://keycloak-service:8080/realms/teehr/protocol/openid-connect/token
          - --oidc-jwks-url=http://keycloak-service:8080/realms/teehr/protocol/openid-connect/certs
          - --client-id=prefect-oauth2-proxy
          - --scope=openid profile email
          - --allowed-group=prefect-admin
          - --oidc-groups-claim=groups
          - --email-domain=*
          - --cookie-secure=true
          - --cookie-samesite=lax
          - --reverse-proxy=true
          - --skip-provider-button=true
          - --set-xauthrequest=true
        env:
          - name: OAUTH2_PROXY_CLIENT_SECRET
            valueFrom:
              secretKeyRef:
                name: prefect-oidc-secrets
                key: client-secret
          - name: OAUTH2_PROXY_COOKIE_SECRET
            valueFrom:
              secretKeyRef:
                name: prefect-oidc-secrets
                key: cookie-secret
        ports:
          - containerPort: 4180
            name: http
        readinessProbe:
          httpGet:
            path: /ping
            port: 4180
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          successThreshold: 1
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /ping
            port: 4180
          initialDelaySeconds: 30
          periodSeconds: 15
          timeoutSeconds: 5
          successThreshold: 1
          failureThreshold: 3
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
---
apiVersion: v1
kind: Service
metadata:
  name: prefect-oauth2-proxy
  namespace: ${environment.namespace}
  labels:
    app: prefect-oauth2-proxy
spec:
  selector:
    app: prefect-oauth2-proxy
  ports:
    - name: http
      port: 4180
      targetPort: 4180
