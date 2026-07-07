# Platform-App Deployment Contract

Last updated: 2026-07-07

This document defines the minimum platform-provided values required by app deployment automation in this repository.

## Platform-Owned Remote Prerequisites

For remote environments, the following components are treated as platform-owned prerequisites:

- cert-manager installation and CRDs
- ClusterIssuer (for example `letsencrypt-prod`)
- Contour installation and CRDs

The app repository should not install these components in remote deploys. It only validates their presence and deploys app resources that depend on them.

Current status:

- cert-manager remote ownership moved to platform repo
- contour remote ownership moved to platform repo
- autoscaler remote ownership moved to platform repo

## Contract Source

For remote deploys, the GitHub Actions workflow expects a YAML file at:

- configs/deploy.remote-aws-srvs.yaml

In CI this file is generated from the `REMOTE_DEPLOY` secret.

## Required Keys

The following keys are required and validated in CI before deployment:

- clusterArn
- clusterRoleArn
- actionRoleArn
- awsRegion
- clusterName

## Example

```yaml
clusterArn: arn:aws:eks:us-east-2:111122223333:cluster/teehr-hub
clusterRoleArn: arn:aws:iam::111122223333:role/teehr-hub-teehr-hub-admin
actionRoleArn: arn:aws:iam::111122223333:role/teehr-hub-github-actions-garden-deploy
awsRegion: us-east-2
clusterName: teehr-hub
```

## Validation

Contract validation script:

- scripts/validate-deploy-contract.sh

Preflight checks for platform prerequisites (Contour/cert-manager/issuer/TLS):

- scripts/check-platform-prereqs.sh

The deploy workflow runs both checks before Garden deployment.
