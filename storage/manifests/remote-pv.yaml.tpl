apiVersion: v1
kind: PersistentVolume
metadata:
  name: teehr-hub-data-nfs
  namespace: ${environment.namespace}
spec:
  capacity:
    storage: 1Mi
  accessModes:
    - ReadWriteMany
  nfs:
    server: ${var.nfsServerDns}
    path: "/teehr-hub"
  mountOptions:
        - rsize=1048576
        - wsize=1048576
        - timeo=600
        - soft # We pick soft over hard, so NFS lockups don't lead to hung processes
        - retrans=2
        - noresvport

