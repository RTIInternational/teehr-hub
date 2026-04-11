# apiVersion: projectcontour.io/v1
# kind: HTTPProxy
# metadata:
#   name: grafana-httpproxy
#   namespace: ${environment.namespace}
# spec:
#   virtualhost:
#     fqdn: grafana.${var.hostname}
#     tls:
#       secretName: grafana.${var.hostname}-tls
#   routes:
#   - conditions:
#     - prefix: /
#     services:
#     - name: kube-prometheus-stack-grafana
#       port: 80
