apiVersion: projectcontour.io/v1
kind: HTTPProxy
metadata:
  name: minio-httpproxy
  namespace: ${environment.namespace}
spec:
  virtualhost:
    fqdn: minio.${var.hostname}
    tls:
      secretName: minio.${var.hostname}-tls
  routes:
  - services:
    - name: minio
      port: 9000
    conditions:
    - prefix: /
    # timeoutPolicy:
    #   response: 300s
    #   idle: 300s
  - services:
    - name: minio
      port: 9001
    conditions:
    - prefix: /ui
    # timeoutPolicy:
    #   response: 60s
    #   idle: 60s
    enableWebsockets: true
    pathRewritePolicy:
      replacePrefix:
      - prefix: /ui
        replacement: /