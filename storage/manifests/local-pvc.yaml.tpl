apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-nfs
  namespace: ${environment.namespace}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: ""