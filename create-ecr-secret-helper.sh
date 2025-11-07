#bin/bash
kubectl --namespace default create secret generic ecr-config \
  --from-file=.dockerconfigjson=./config.json \
  --type=kubernetes.io/dockerconfigjson