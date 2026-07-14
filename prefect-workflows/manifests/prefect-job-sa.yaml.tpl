apiVersion: v1
kind: ServiceAccount
metadata:
  name: prefect-job
  namespace: ${environment.namespace}
  ${if environment.name == "remote"}
  annotations:
    eks.amazonaws.com/role-arn: ${var.irsa.icebergReadWriteRoleArn}
  ${endif}