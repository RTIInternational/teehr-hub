apiVersion: v1
kind: ServiceAccount
metadata:
  name: xpublish-api
  ${if environment.name == "remote"}
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::935462133478:role/teehr-hub-iceberg-s3-warehouse-readonly-irsa
  ${endif}
