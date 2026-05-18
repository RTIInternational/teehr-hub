apiVersion: projectcontour.io/v1
kind: HTTPProxy
metadata:
  name: prefect-httpproxy
  namespace: ${environment.namespace}
spec:
  virtualhost:
    fqdn: prefect.${var.hostname}
    tls:
      secretName: prefect.${var.hostname}-tls
  routes:
  - conditions:
    - prefix: /
    services:
    - name: prefect-oauth2-proxy
      port: 4180
    enableWebsockets: true
    timeoutPolicy:
      response: 300s
      idle: 300s
