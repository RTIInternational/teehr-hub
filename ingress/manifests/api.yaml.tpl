apiVersion: projectcontour.io/v1
kind: HTTPProxy
metadata:
  name: api-httpproxy
  namespace: ${environment.namespace}
spec:
  virtualhost:
    fqdn: api.${var.hostname}
    tls:
      secretName: api.${var.hostname}-tls
  routes:
  - conditions:
    - prefix: /
    services:
    - name: teehr-api
      port: 8000
    enableWebsockets: true
    timeoutPolicy:
      response: 300s
      idle: 300s