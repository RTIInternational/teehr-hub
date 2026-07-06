#!/bin/sh
set -o errexit

# Get the absolute path to the project root (assuming this script is in kind/ subdirectory)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_PATH="${PROJECT_ROOT}/data"

echo "📁 Project root: ${PROJECT_ROOT}"
echo "💾 Data path: ${DATA_PATH}"

# Ensure data directory exists
mkdir -p "${DATA_PATH}"

# 1. Create registry container unless it already exists
reg_name='kind-registry'
reg_port='5001'
if [ "$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)" != 'true' ]; then
  docker run \
    -d --restart=always -p "127.0.0.1:${reg_port}:5000" --network bridge --name "${reg_name}" \
    registry:2
fi

# 2. Create kind cluster with containerd registry config dir enabled
# TODO: kind will eventually enable this by default and this patch will
# be unnecessary.
#
# See:
# https://github.com/kubernetes-sigs/kind/issues/2875
# https://github.com/containerd/containerd/blob/main/docs/cri/config.md#registry-configuration
# See: https://github.com/containerd/containerd/blob/main/docs/hosts.md
cat <<EOF | kind create cluster --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry]
    config_path = "/etc/containerd/certs.d"
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
  extraMounts:
  - hostPath: ${DATA_PATH}
    containerPath: /data
# worker: core
- role: worker
  labels:
    teehr-hub/nodegroup-name: core-a
    hub.jupyter.org/node-purpose: core
    k8s.dask.org/node-purpose: core
    node.kubernetes.io/instance-type: r5.xlarge
  extraMounts:
  - hostPath: ${DATA_PATH}
    containerPath: /data
# worker2: nb-r5-xlarge
- role: worker
  labels:
    teehr-hub/nodegroup-name: nb-r5-xlarge
    hub.jupyter.org/node-purpose: user
    k8s.dask.org/node-purpose: scheduler
    node.kubernetes.io/instance-type: r5.xlarge
  extraMounts:
  - hostPath: ${DATA_PATH}
    containerPath: /data
# worker3: spark-r5-4xlarge
- role: worker
  labels:
    teehr-hub/nodegroup-name: spark-r5-4xlarge
    node.kubernetes.io/instance-type: r5.4xlarge
  extraMounts:
  - hostPath: ${DATA_PATH}
    containerPath: /data
EOF

# 3. Add the registry config to the nodes
#
# This is necessary because localhost resolves to loopback addresses that are
# network-namespace local.
# In other words: localhost in the container is not localhost on the host.
#
# We want a consistent name that works from both ends, so we tell containerd to
# alias localhost:${reg_port} to the registry container when pulling images
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${reg_port}"
for node in $(kind get nodes); do
  docker exec "${node}" mkdir -p "${REGISTRY_DIR}"
  cat <<EOF | docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"
[host."http://${reg_name}:5000"]
EOF
done

# 4. Connect the registry to the cluster network if not already connected
# This allows kind to bootstrap the network but ensures they're on the same network
if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${reg_name}")" = 'null' ]; then
  docker network connect "kind" "${reg_name}"
fi

# 5. Document the local registry
# https://github.com/kubernetes/enhancements/tree/master/keps/sig-cluster-lifecycle/generic/1755-communicating-a-local-registry
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${reg_port}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

# kind-worker2 acts as a JupyterHub user node (tainted like EKS nb-r5-xlarge)
kubectl taint nodes kind-worker2 hub.jupyter.org/dedicated=user:NoSchedule
kubectl taint nodes kind-worker2 hub.jupyter.org_dedicated=user:NoSchedule

#kind-worker3 acts as Spark worker node (tainted like EKS spark-r5-4xlarge)
kubectl taint nodes kind-worker3 teehr-hub/dedicated=worker:NoSchedule
kubectl taint nodes kind-worker3 teehr-hub_dedicated=worker:NoSchedule

# Setup ingress with Contour
kubectl apply -f https://projectcontour.io/quickstart/contour.yaml
kubectl patch daemonsets -n projectcontour envoy -p '{"spec":{"template":{"spec":{"nodeSelector":{"ingress-ready":"true"},"tolerations":[{"key":"node-role.kubernetes.io/control-plane","operator":"Equal","effect":"NoSchedule"},{"key":"node-role.kubernetes.io/master","operator":"Equal","effect":"NoSchedule"}]}}}}'
