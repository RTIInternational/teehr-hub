apiVersion: v1
kind: ServiceAccount
metadata:
  name: jupyter
  namespace: ${environment.namespace}
  annotations:
    eks.amazonaws.com/role-arn: ${var.irsa.icebergReadOnlyRoleArn}
  labels:
    app: jupyterhub
    component: jupyter