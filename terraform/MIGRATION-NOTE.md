# Terraform Migration Note (Phase 1)

Terraform ownership is transitioning to the `teehr-platform` repository.

Current status:
- `teehr-platform/terraform` is the active location for new Terraform changes.
- This `teehr-hub/terraform` directory is retained temporarily to avoid breaking existing workflows during migration.

Guidance:
- Make Terraform updates in `teehr-platform`.
- Use backend config files with `terraform init -backend-config=...` in `teehr-platform/terraform`.
- Avoid introducing new Terraform changes in this directory unless required for emergency fixes during cutover.
