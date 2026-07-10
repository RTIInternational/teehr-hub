# JupyterHub Remote Profiles (Deployment Repo)

This directory owns the remote JupyterHub profile list for this deployment
repository.

## Why this exists

`jupyterhub/garden.yaml` supports loading profile definitions from the
`JUPYTERHUB_PROFILE_LIST_JSON` environment variable.

- If set, it overrides static `singleuser.profileList` in Helm values.
- If not set, static Helm values are used.

## Repository split

Ownership is split across repos:

- `teehr-cloud-core/jupyterhub-profiles`:
   - Contract and generator logic.
   - Local profile payload and template.
- `teehr-hub/jupyterhub-profiles` (this directory):
   - Remote project list input for this deployment.
   - Generated remote payload and ConfigMap template used by deployment.

## Contract (v1)

Top-level JSON can be either:

1. A list of JupyterHub profile objects.
2. An object with:
   - `version`: optional; if present, must be `1`.
   - `profiles`: required list of JupyterHub profile objects.

Minimum required key per profile:
- `display_name` (string)

All other keys are passed through to JupyterHub/KubeSpawner unchanged.

## Files in this directory

- Source of truth for remote projects:
   - `profile-list.remote.projects.json`
- Generated remote payload:
   - `profile-list.remote.json`
- Generated remote ConfigMap template:
   - `manifests/jupyterhub-profile-list-remote.configmap.yaml.tpl`
- Generator scripts (owned in submodule):
   - `teehr-cloud-core/jupyterhub-profiles/generate_profile_list.py`
   - `teehr-cloud-core/jupyterhub-profiles/generate_profile_configmap_templates.py`

## Update flow

When adding/changing remote profiles for this deployment:

1. Update the `teehr-cloud-core` submodule to the desired version.
2. Edit `profile-list.remote.projects.json`.
3. From the deployment repo root run:

```bash
python3 teehr-cloud-core/jupyterhub-profiles/generate_profile_list.py \
   --spec jupyterhub-profiles/profile-list.remote.projects.json \
   --out jupyterhub-profiles/profile-list.remote.json

python3 teehr-cloud-core/jupyterhub-profiles/generate_profile_configmap_templates.py \
   --spec jupyterhub-profiles/profile-list.remote.json \
   --out jupyterhub-profiles/manifests/jupyterhub-profile-list-remote.configmap.yaml.tpl
```

4. Commit these files together:
    - `profile-list.remote.projects.json`
    - `profile-list.remote.json`
    - `manifests/jupyterhub-profile-list-remote.configmap.yaml.tpl`
5. Run the normal remote Garden deploy flow so the ConfigMap deploys before
    JupyterHub.

Because the env var source is optional, deployment still works without the
ConfigMap, but profile customization will not be applied.

## Notes

- This repo is remote-only for profiles. No local profile payload is required.
- Generator logic is intentionally centralized in
   `teehr-cloud-core/jupyterhub-profiles` to avoid drift.
