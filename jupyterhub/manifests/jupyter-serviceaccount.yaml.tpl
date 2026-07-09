apiVersion: v1
kind: ServiceAccount
metadata:
  name: jupyter
  namespace: ${environment.namespace}
  ${if environment.name == "remote"}
  annotations:
    eks.amazonaws.com/role-arn: ${var.irsa.icebergReadOnlyRoleArn}
  ${endif}
  labels:
    app: jupyterhub
    component: jupyter