apiVersion: projectcontour.io/v1
kind: HTTPProxy
metadata:
  name: panel-httpproxy
  namespace: ${environment.namespace}
spec:
  virtualhost:
    fqdn: panel.${var.hostname}
    tls:
      secretName: panel.${var.hostname}-tls
  routes:
  - conditions:
    - prefix: /
    services:
    - name: panel-app
      port: 5006
    enableWebsockets: true
    timeoutPolicy:
      response: 300s
      idle: 300s