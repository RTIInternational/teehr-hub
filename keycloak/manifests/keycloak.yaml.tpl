apiVersion: k8s.keycloak.org/v2alpha1
kind: Keycloak
metadata:
  name: keycloak
spec:
  instances: 1
  startOptimized: false
  image: ${actions.build.keycloak-theme.outputs.deploymentImageId}
  db:
    vendor: postgres
    host: keycloak-pg
    database: keycloak
    usernameSecret:
      name: keycloak-db-secrets
      key: username
    passwordSecret:
      name: keycloak-db-secrets
      key: password
  http:
    httpEnabled: true
  ingress:
    enabled: false
  hostname:
    hostname: https://auth.${var.hostname}
    strict: false
    backchannelDynamic: false
  proxy:
    headers: xforwarded
  bootstrapAdmin:
    user:
      secret: keycloak-admin-secrets
  resources:
    requests:
      cpu: 250m
      memory: 1Gi
    limits:
      cpu: "1"
      memory: 2Gi
