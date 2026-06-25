apiVersion: projectcontour.io/v1
kind: HTTPProxy
metadata:
  name: xpublish-api-httpproxy
  namespace: ${environment.namespace}
spec:
  virtualhost:
    fqdn: xpublish-api.${var.hostname}
    tls:
      secretName: xpublish-api.${var.hostname}-tls
  routes:
  - conditions:
    - prefix: /
    services:
    - name: xpublish-api
      port: 8000
    enableWebsockets: true
    timeoutPolicy:
      response: 300s
      idle: 300s
