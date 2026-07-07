# TEEHR Hub Infrastructure and Application Split Plan

Last updated: 2026-07-06

## Objective
Separate platform infrastructure from application deployment so TEEHR Hub can be deployed across multiple hosts/accounts with different AWS requirements, while keeping local development productive.

## Scope
Infrastructure components to move out of the application delivery path first:
- Terraform
- Autoscaler
- Contour
- Cert-manager

Related follow-on items in the same migration wave:
- Account-specific IAM role wiring (IRSA annotations in app manifests)
- Cluster/account-specific values in Garden project config

## Why This Split Is Needed
Current repo mixes platform and app concerns, and includes account-specific values in app deployment paths.

Examples:
- Hardcoded account/context in Garden provider config: [project.garden.yml](project.garden.yml#L75)
- Cluster autoscaler chart values hardcode cluster, region, and role ARN: [autoscaler/garden.yaml](autoscaler/garden.yaml#L16)
- App service accounts hardcode IRSA role ARNs: [jupyterhub/manifests/jupyter-serviceaccount.yaml.tpl](jupyterhub/manifests/jupyter-serviceaccount.yaml.tpl#L7)
- Ingress deploys depend directly on contour/cert-manager modules: [ingress/garden.yaml](ingress/garden.yaml#L8)
- Terraform backend bucket/region are hardcoded: [terraform/versions.tf](terraform/versions.tf#L15)

## Target Architecture
Use a 2-repo model with clear interfaces.

### 1) Platform Repo (new)
Owns account/cluster foundational concerns:
- Terraform for VPC, EKS, IAM, ECR, EFS, S3, OIDC, IRSA role creation
- Kubernetes platform add-ons:
  - cert-manager
  - contour
  - cluster-autoscaler
- Environment bootstrap outputs/artifacts consumed by app repo

Suggested name: teehr-platform

### 2) Application Repo (current teehr-hub)
Owns application workloads only:
- API, frontend, jupyterhub, spark, trino, prefect, keycloak, dashboards
- Ingress routes for app endpoints (HTTPProxy resources) but not ingress controller installation
- No account IDs, role ARNs, or cluster bootstrap logic hardcoded

## Contract Between Platform and Application
Define a small, versioned contract that platform publishes and app consumes.

Required contract values:
- cluster_name
- cluster_region
- kube_context_name
- ingress_class_name (for contour)
- certificate_issuer_name (for cert-manager)
- namespace defaults per environment
- IRSA role ARNs (or role names) per workload identity:
  - iceberg_rw_role_arn
  - iceberg_ro_role_arn
  - autoscaler_role_arn (platform only)

Preferred transport:
- Option A: SSM Parameter Store paths (per environment)
- Option B: Generated values file committed to environment repo (or encrypted secret store)
- Option C: Terraform outputs consumed by CI and rendered into Garden variables

Recommendation: Start with Terraform outputs + CI rendering into Garden variables, then optionally move to SSM.

## Phased Migration Plan

## Phase 0: Stabilize Interfaces (1-2 days)
- Inventory all account-specific values in manifests and Garden files.
- Add a single values schema document for platform-to-app contract.
- Introduce app variables for currently hardcoded values (no behavior change yet).

Deliverables:
- Contract document in docs
- Initial variable plumbing in app manifests

## Phase 1: Extract Terraform (3-5 days)
- Move [terraform](terraform) into new platform repo.
- Parameterize backend config (bucket/key/region) per environment/account.
- Keep current Terraform module composition initially; do not redesign infra and split at once.
- Publish required outputs for app consumption.

Deliverables:
- Platform repo with terraform state separation by environment/account
- CI job that runs plan/apply with environment-specific varfiles
- Output artifact for app deploy pipeline

## Phase 2: Extract Platform Add-ons (2-3 days)
- Move [autoscaler](autoscaler), [contour](contour), and [cert-manager](cert-manager) to platform repo.
- Platform pipeline deploy order:
  1. cert-manager
  2. contour
  3. autoscaler
- Remove these modules from app deployment workflow.

Deliverables:
- Platform add-on deployment pipeline
- Versioned add-on manifests/charts managed independently from app releases

## Phase 3: Decouple App from Account IDs (3-4 days)
- Replace hardcoded ARNs/account IDs in app manifests with variables sourced from contract.
- Remove hardcoded AWS account/cluster context from [project.garden.yml](project.garden.yml).
- Keep local environment defaults intact where feasible.

Deliverables:
- App repo deployable to any prepared cluster/account via supplied contract values
- Environment overlays/varfiles for local, dev, staging, prod

## Phase 4: Rewire Ingress Dependencies (1-2 days)
- Keep ingress route resources in app repo.
- Remove direct Garden dependencies on add-on modules and replace with preflight checks or documented prerequisites.
- Make issuer and ingress class configurable values.

Deliverables:
- Ingress deploys independent of controller installation ownership
- Clear failure mode if platform prerequisites are missing

## Phase 5: CI/CD and Promotion Model (2-3 days)
- Separate pipelines:
  - Platform pipeline (slower cadence, stricter controls)
  - App pipeline (faster cadence)
- Add environment promotion gates and compatibility checks between platform and app contract versions.

Deliverables:
- Compatibility matrix (platform version X supports app version range Y)
- Documented rollout and rollback for both repos

## Proposed Ownership Model
- Platform team (or infra maintainers): terraform, autoscaler, contour, cert-manager
- App team: all workload modules and app ingress objects
- Shared responsibility: contract schema and versioning

## Definition of Done
- App deployment requires no hardcoded AWS account IDs or role ARNs.
- App can deploy to at least two distinct AWS accounts with different role names/IDs using only environment inputs.
- Platform and app can be released independently.
- Local kind development remains supported without platform repo dependency.

## Risks and Mitigations
- Risk: Breaking ingress during ownership handoff.
  - Mitigation: Keep app HTTPProxy objects in app repo; migrate controller ownership only.
- Risk: IRSA drift between platform outputs and app manifests.
  - Mitigation: Contract validation step in app CI before deploy.
- Risk: Terraform state migration mistakes.
  - Mitigation: One-time state migration runbook and backup before cutover.

## Immediate Backlog (Recommended Next 10 Tasks)
1. Add platform contract schema doc and example values file.
2. Add Garden variables for role ARNs, region, cluster name, ingress class, issuer name.
3. Replace autoscaler hardcoded role/region/cluster in [autoscaler/garden.yaml](autoscaler/garden.yaml).
4. Replace IRSA hardcoded annotations in jupyterhub/spark/trino/prefect/iceberg manifests.
5. Parameterize Terraform backend in [terraform/versions.tf](terraform/versions.tf).
6. Create new platform repo with moved terraform directory.
7. Move cert-manager and contour modules to platform repo.
8. Move autoscaler module to platform repo.
9. Remove platform module dependencies from [ingress/garden.yaml](ingress/garden.yaml).
10. Add CI compatibility check that validates required contract values before app deploy.

## Open Decisions
- Should platform outputs be delivered through SSM, secrets manager, or CI-rendered varfiles?
- Should ingress route manifests stay in app repo long-term, or move to a shared edge repo?
- Do we want a non-AWS host path now (for example, AKS/GKE), or defer until AWS multi-account is complete?
