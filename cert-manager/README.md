# cert-manager (Local Only)

This module exists only for local development in teehr-hub.

Scope:
- Local Kind/Garden workflow only
- Installs cert-manager locally
- Applies local issuer and certificate resources for local hostnames

Not in scope:
- Remote/shared cluster cert-manager installation
- Remote issuer lifecycle
- Platform-level certificate infrastructure ownership

Remote ownership:
- For remote environments, cert-manager is platform-owned in teehr-cloud-platform.
- Do not use this directory to manage remote cert-manager resources.

Operational note:
- This module is constrained to local environment targets in garden config.
