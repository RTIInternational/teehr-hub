# Changelog

## 2026-07-07

### Summary
- Completed post-migration cleanup in the app repo after platform infrastructure code moved to `teehr-platform`.
- Removed platform-oriented and remote-only artifacts that no longer belong in `teehr-hub`.
- Updated docs to clarify local app workflow vs. remote platform responsibilities.

### What Changed
- Removed `teehr-hub` Terraform directory after code was moved to the platform repo.
- Removed migrated platform modules for autoscaler and contour.
- Removed remote cert-manager for remote usage in this repo while leaving the local path.
- Cleaned stale references in docs/configs and removed no-longer-needed helper/config files tied to old flow.

### Why
- Split the application code from the platform code to allow the application to more cleanly be extended to other platforms. 
- Keep `teehr-hub` focused on application deployment and local development workflows.
