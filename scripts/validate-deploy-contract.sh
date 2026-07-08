#!/usr/bin/env bash
set -euo pipefail

# Validates the deployment contract file consumed by the remote deploy workflow.
# Fails fast when required keys are missing or empty.

CONFIG_PATH="${1:-configs/deploy.remote-aws-srvs.yaml}"

if ! command -v yq >/dev/null 2>&1; then
  echo "ERROR: yq is required for contract validation."
  exit 1
fi

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "ERROR: Deployment contract file not found: $CONFIG_PATH"
  exit 1
fi

required_keys=(
  "clusterArn"
  "clusterRoleArn"
  "actionRoleArn"
  "awsRegion"
  "clusterName"
)

failures=0

for key in "${required_keys[@]}"; do
  value="$(yq eval ".${key}" "$CONFIG_PATH")"
  if [[ -z "$value" || "$value" == "null" ]]; then
    echo "FAIL: Required key '${key}' is missing or empty in ${CONFIG_PATH}"
    failures=$((failures + 1))
  else
    echo "PASS: ${key} is set"
  fi
done

if [[ "$failures" -gt 0 ]]; then
  echo ""
  echo "Deployment contract validation failed with ${failures} issue(s)."
  exit 1
fi

echo ""
echo "Deployment contract validation passed."
