# v1 Prefect flows

Flows for the v1 warehouse (ADR-0019 in teehr-cloud-core), apart from the legacy flows: their
own image (`Dockerfile`: teehr-core's warehouse writer and builders, Prefect; no legacy
`teehr`, Spark or JVM), deployer job and deployments (`prefect-local.yaml`,
`prefect-remote.yaml`), on the shared `kubernetes-pool`. They act as the
`teehr-platform-automation` service account, a write member of `public` and `platform`
(ADR-0020 in teehr-cloud-core), for both table writes and control-plane calls.

- `flows/derived.py`: build a derived dataset (percentiles, climatology, naive scale) of an
  observed timeseries. Register the dataset first:
  `teehr datasets create usgs_streamflow_percentiles -p public --kind percentiles --observed usgs_streamflow`.
- `flows/evaluations.py`: run a project's evaluations (default: all of `platform`, the specs in
  `evaluations/platform/`) through the control plane, one at a time, waiting for each.
  Deployed as `run-platform-evaluations` (daily, starts paused: run it once by hand from the
  Prefect UI before turning on its schedule). Runs act as their caller, so they show
  `service-account-teehr-platform-automation` as their creator.
- `tests/smoke_derived.py`: the flow against a throwaway local catalog, in the image.
- `tests/smoke_evaluations.py`: the run-evaluations flow against a fake control plane.

## Credentials

The client's secret is `automation-client-secret` in `control-plane-secrets` (remote: in
`REMOTE_SECRETS`). The Keycloak bootstrap sets it on the client, and `load-secrets` copies it
into the Prefect Secret block `teehr-platform-automation-secret`, which the flows load (so it
isn't in the deployments' job variables). After changing it, redeploy both. Its write membership is the control plane's `SYSTEM_PROJECT_WRITERS`, restored on
every restart.

The image's teehr-core commit is `teehrCoreVersion` in `project.garden.yml` (a var change
needs `garden deploy prefect-v1-workflow-deploy --force`).
