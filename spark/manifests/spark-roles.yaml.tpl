apiVersion: v1
kind: ServiceAccount
metadata:
  name: spark
  namespace: ${environment.namespace}
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::935462133478:role/teehr-hub-iceberg-s3-warehouse-readonly-irsa
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: spark-role
  namespace: ${environment.namespace}
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps", "persistentvolumeclaims", "secrets"]
  verbs: ["create", "get", "list", "watch", "delete", "deletecollection", "patch", "update"]
- apiGroups: ["batch", "extensions"]
  resources: ["jobs"]
  verbs: ["create", "get", "list", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["create", "get", "list", "watch", "delete"]
- apiGroups: ["extensions", "networking.k8s.io"]
  resources: ["ingresses"]
  verbs: ["create", "get", "list", "watch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: spark-role-binding
  namespace: ${environment.namespace}
roleRef:
  kind: Role
  name: spark-role
  apiGroup: rbac.authorization.k8s.io
subjects:
- kind: ServiceAccount
  name: spark
  namespace: ${environment.namespace}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: spark-cluster-role
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps", "secrets"]
  verbs: ["create", "get", "list", "watch", "delete", "patch", "update"]
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["storage.k8s.io"]
  resources: ["storageclasses"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: spark-cluster-role-binding
roleRef:
  kind: ClusterRole
  name: spark-cluster-role
  apiGroup: rbac.authorization.k8s.io
subjects:
- kind: ServiceAccount
  name: spark
  namespace: ${environment.namespace}
