apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-nfs
  namespace: ${environment.namespace}
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 1Mi
  storageClassName: ""
  volumeName: teehr-hub-data-nfs