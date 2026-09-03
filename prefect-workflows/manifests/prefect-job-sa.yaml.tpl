# On remote, the prefect-job SA carries an IRSA role covering only non-catalog
# S3 access (icechunk). Iceberg warehouse access comes from Polaris-vended
# credentials via POLARIS_USE_STS, not from this role. Guarded so the SA still
# deploys to `local`, which defines no irsa vars.
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prefect-job
  namespace: ${environment.namespace}
  ${if environment.name == "remote"}
  annotations:
    eks.amazonaws.com/role-arn: ${var.irsa.prefectJobRoleArn}
  ${endif}
