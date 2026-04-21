apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ${var.hostname}-hub-cert
spec:
  commonName: hub.${var.hostname}
  dnsNames:
  - hub.${var.hostname}
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  secretName: hub.${var.hostname}-tls
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ${var.hostname}-minio-cert
spec:
  commonName: minio.${var.hostname}
  dnsNames:
  - minio.${var.hostname}
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  secretName: minio.${var.hostname}-tls
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ${var.hostname}-panel-cert
spec:
  commonName: panel.${var.hostname}
  dnsNames:
  - panel.${var.hostname}
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  secretName: panel.${var.hostname}-tls
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ${var.hostname}-api-cert
spec:
  commonName: api.${var.hostname}
  dnsNames:
  - api.${var.hostname}
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  secretName: api.${var.hostname}-tls
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ${var.hostname}-dashboards-cert
spec:
  commonName: dashboards.${var.hostname}
  dnsNames:
  - dashboards.${var.hostname}
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  secretName: dashboards.${var.hostname}-tls