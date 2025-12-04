apiVersion: projectcontour.io/v1
kind: HTTPProxy
metadata:
  name: jupyterhub-httpproxy
  namespace: ${environment.namespace}
spec:
  virtualhost:
    fqdn: hub.${var.hostname}
    tls:
      secretName: hub.${var.hostname}-tls
  routes:
  - conditions:
    - prefix: /
    services:
    - name: proxy-public
      port: 80
    enableWebsockets: true