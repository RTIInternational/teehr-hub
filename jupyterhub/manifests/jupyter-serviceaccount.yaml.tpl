apiVersion: v1
kind: ServiceAccount
metadata:
  name: jupyter
  namespace: ${environment.namespace}
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::794457362858:role/fved-iceberg-s3-warehouse-readonly-irsa
  labels:
    app: jupyterhub
    component: jupyter