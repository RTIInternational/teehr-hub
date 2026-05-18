apiVersion: projectcontour.io/v1
kind: HTTPProxy
metadata:
  name: auth-httpproxy
  namespace: ${environment.namespace}
spec:
  virtualhost:
    fqdn: auth.${var.hostname}
    tls:
      secretName: auth.${var.hostname}-tls
  routes:
  - conditions:
    - prefix: /
    services:
    - name: keycloak-service
      port: 8080
