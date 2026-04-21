apiVersion: v1
kind: ServiceAccount
metadata:
  name: jupyter
  namespace: ${environment.namespace}
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::935462133478:role/teehr-hub-iceberg-s3-warehouse-readonly-irsa
  labels:
    app: jupyterhub
    component: jupyter