apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ${var.hostname}-dashboards-cert
spec:
  commonName: dashboards.${var.hostname}
  dnsNames:
  - dashboards.${var.hostname}
  issuerRef:
    name: ${var.certificateIssuerName}
    kind: ClusterIssuer
  secretName: dashboards.${var.hostname}-tls
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
    name: ${var.certificateIssuerName}
    kind: ClusterIssuer
  secretName: panel.${var.hostname}-tls
