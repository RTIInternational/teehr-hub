#!/usr/bin/env bash
set -euo pipefail

# Creates (or updates) the ecr-config secret that Garden uses to push and pull
# images from ECR (project.garden.yml imagePullSecrets). Run once per new
# cluster, before its first deploy.
#
# Usage: CONTEXT=<kube-context> ./create-ecr-secret-helper.sh

: "${CONTEXT:?set CONTEXT to the kube context of the cluster}"
cd "$(dirname "$0")"
kubectl --context "$CONTEXT" --namespace default \
  create secret generic ecr-config \
  --from-file=.dockerconfigjson=./config.json \
  --type=kubernetes.io/dockerconfigjson \
  --dry-run=client -o yaml \
  | kubectl --context "$CONTEXT" apply -f -
