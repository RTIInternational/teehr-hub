apiVersion: v1
kind: ConfigMap
metadata:
  name: prefect-oauth2-proxy-pages
  namespace: ${environment.namespace}
data:
  error.html: |
    <!DOCTYPE html>
    <html>
    <head>
      <title>Prefect Access</title>
      <style>
        body {
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif;
          margin: 0;
          padding: 0;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .container {
          background: white;
          border-radius: 12px;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
          max-width: 500px;
          padding: 40px;
          text-align: center;
        }
        h1 {
          color: #333;
          margin: 0 0 16px 0;
          font-size: 28px;
        }
        .status-code {
          font-size: 48px;
          color: #667eea;
          margin: 24px 0;
          font-weight: bold;
        }
        p {
          color: #666;
          line-height: 1.6;
          margin: 12px 0;
          font-size: 16px;
        }
        .button-group {
          margin-top: 32px;
          display: flex;
          gap: 12px;
          justify-content: center;
          flex-wrap: wrap;
        }
        .button {
          padding: 10px 20px;
          border-radius: 6px;
          text-decoration: none;
          font-weight: 600;
          transition: all 0.3s ease;
          border: none;
          cursor: pointer;
          font-size: 14px;
        }
        .button-primary {
          background: #667eea;
          color: white;
        }
        .button-primary:hover {
          background: #5568d3;
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        .button-secondary {
          background: #f0f0f0;
          color: #333;
          border: 1px solid #ddd;
        }
        .button-secondary:hover {
          background: #e8e8e8;
        }
        .error-details {
          background: #f5f5f5;
          border-left: 4px solid #667eea;
          padding: 16px;
          margin-top: 24px;
          text-align: left;
          border-radius: 4px;
        }
        .error-details p {
          margin: 0;
          font-size: 14px;
          color: #555;
        }
        .footer {
          margin-top: 24px;
          font-size: 12px;
          color: #999;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <h1>Prefect Access Restricted</h1>
        <div class="status-code">{{.Status}}</div>
        <p>You do not have permission to access Prefect.</p>
        <p>Only members of the <strong>prefect-admin</strong> group can access this service.</p>
        
        <div class="button-group">
          <button class="button button-primary" onclick="window.location.href='https://auth.teehr.local.app.garden/realms/teehr/account';">Manage Account</button>
          <button class="button button-secondary" onclick="window.history.back();">Go Back</button>
        </div>
        
        <div class="error-details">
          <p><strong>What's happening?</strong></p>
          <p>Your current user account is not in the prefect-admin group. Please contact your system administrator to request access.</p>
        </div>
        
        <div class="footer">
          <p>Prefect Admin Portal &bull; {{.RequestHost}}</p>
        </div>
      </div>
    </body>
    </html>
---
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
          - --custom-templates-dir=/etc/oauth2-proxy/templates
        volumeMounts:
          - name: templates
            mountPath: /etc/oauth2-proxy/templates
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
      volumes:
        - name: templates
          configMap:
            name: prefect-oauth2-proxy-pages
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
