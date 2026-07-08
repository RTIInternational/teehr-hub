# JupyterHub Profile List Contract

This directory defines the client-owned profile contract for JupyterHub spawn options.

## Why this exists

`jupyterhub/garden.yaml` now supports loading profile definitions from the
`JUPYTERHUB_PROFILE_LIST_JSON` environment variable.

When this env var is set, the loaded profile list overrides the static
`singleuser.profileList` in Helm values. If it is not set, the static profile
list is used as a fallback.

## Contract (v1)

Top-level JSON can be either:

1. A list of JupyterHub profile objects.
2. An object with:
   - `version`: must be `1` when present.
   - `profiles`: a list of JupyterHub profile objects.

Minimum required key per profile:
- `display_name` (string)

Everything else is passed through to JupyterHub/KubeSpawner unchanged.

## Delivery pattern for client repos

Recommended pattern in a client repo:

1. Create a ConfigMap named `jupyterhub-profile-list`.
2. Add a key `profile-list.json` containing contract JSON.
3. Deploy that ConfigMap before `teehr-jupyterhub`.

Because the env var source is marked optional, deployments continue to work
without this ConfigMap.

## Example

See `profile-list.example.json` in this folder.

## Suggested migration sequence

1. Copy current profile list into client JSON.
2. Deploy ConfigMap and verify profile rendering in JupyterHub UI.
3. Remove static `singleuser.profileList` from `garden.yaml` after cutover.
4. Move this contract and loader into `teehr-cloud-core` and keep JSON in each
   client repository.
