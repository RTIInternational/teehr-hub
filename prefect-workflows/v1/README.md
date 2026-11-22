# v1 Prefect flows

Flows for the v1 warehouse (ADR-0019 in teehr-cloud-core), apart from the legacy flows: their
own image (`Dockerfile`: teehr-core's warehouse writer and builders, Prefect; no legacy
`teehr`, Spark or JVM), deployer job and deployments (`prefect-local.yaml`,
`prefect-remote.yaml`), on the shared `kubernetes-pool`. They act as `prefect-polaris`, whose
`teehr-platform-write` role writes `public`.

- `flows/derived.py`: build a derived dataset (percentiles, climatology, naive scale) of an
  observed timeseries. Register the dataset first:
  `teehr datasets create usgs_streamflow_percentiles -p public --kind percentiles --observed usgs_streamflow`.
- `flows/evaluations.py`: run a project's evaluations (default: all of `platform`, the specs in
  `evaluations/platform/`) through the control plane, one at a time, waiting for each.
  Deployed as `run-platform-evaluations` (daily, starts paused). Runs act as their caller, so
  the flow uses a personal token of the platform's automation user (see below).
- `tests/smoke_derived.py`: the flow against a throwaway local catalog, in the image.
- `tests/smoke_evaluations.py`: the run-evaluations flow against a fake control plane.

## The automation user's token

`run-platform-evaluations` calls the control plane as a dedicated Keycloak user (e.g.
`teehr-platform-automation`), a write member of `platform`, through a personal token
(ADR-0018 in teehr-cloud-core). Set it up once, and again before the token expires (offline
sessions last at most a year):

1. Create the user in Keycloak and add it to `platform` with the write role.
2. Make its token, approving in a browser signed in as that user, into a config directory
   of its own (the token is in its `credentials.json`), limited to `platform`:
   `TEEHR_CONFIG_DIR=<empty dir> teehr --api <url> auth login --name prefect-run-platform-evaluations -p platform --days 365 --no-browser`.
3. Put the token in the `prefect-control-plane-token` secret (key `token`): `REMOTE_SECRETS`
   for remote, `secrets.local.private.yaml` for KinD.
4. Redeploy the flows (`prefect-v1-workflow-deploy`): the deployer passes the token to the
   deployment. Without the secret, the flow fails at once and says so.

The image's teehr-core commit is `teehrCoreVersion` in `project.garden.yml` (a var change
needs `garden deploy prefect-v1-workflow-deploy --force`).
