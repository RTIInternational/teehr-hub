# v1 Prefect flows

Flows for the v1 warehouse (ADR-0019 in teehr-cloud-core), apart from the legacy flows: their
own image (`Dockerfile`: teehr-core's warehouse writer and builders, Prefect; no legacy
`teehr`, Spark or JVM), deployer job and deployments (`prefect-local.yaml`,
`prefect-remote.yaml`), on the shared `kubernetes-pool`. They act as the
`teehr-platform-automation` service account, a write member of `public` and `platform`
(ADR-0020 in teehr-cloud-core), for both table writes and control-plane calls.

- `flows/auth.py`: the flows' identity, shared by every flow: the client secret (from the
  Prefect Secret block), and `control_plane()`, an HTTP client for the control plane's API
  that renews its tokens. `flows/catalog.py`: the Polaris catalog, as the same account.
- `flows/derived.py`: build a derived dataset (percentiles, climatology, naive scale) of an
  observed timeseries. Register the dataset first:
  `teehr datasets create usgs_streamflow_percentiles -p public --kind percentiles --observed usgs_streamflow`.
- `flows/evaluations.py`: run a project's evaluations (default: all of `platform`, the specs in
  `evaluations/platform/`) through the control plane, one at a time, waiting for each.
  Deployed as `v1-run-platform-evaluations` (daily, starts paused: run it once by hand from the
  Prefect UI before turning on its schedule). Runs act as their caller, so they show
  `service-account-teehr-platform-automation` as their creator.
- `flows/write.py`: `write_rows`, the one write path for every ingest. A teehr-core source
  (`teehr_core.fetch.*`) fetches however suits it but returns v1 timeseries rows in its `UNIT`;
  `write_rows` drops non-key columns the dataset lacks, joins batches into commits, logs each,
  and writes them with teehr-core's `write_timeseries` (new series added to the series table).
  A new source's flow picks its locations and window, calls the source, then `write_rows`.
- `flows/ingest_usgs.py`: ingest USGS streamflow into `public.usgs_streamflow` for the gages
  of its location layer (or given `sites`), with teehr-core's fetch and writer; the template
  for v1 ingests. Deployed as `v1-ingest-usgs-streamflow` (twice daily on use1).
  Uses the `api-usgs-pat` Secret block when there is one. At sites with several discharge
  time series, teehr-core's `choose_series` ranks them from the USGS's metadata, with the
  flow's `PINS` first, and keeps the best one covering each time.
- `flows/ingest_usgs.py:backfill_usgs_streamflow`: fill a USGS dataset's whole record from the
  USGS bulk Parquet files (staged by month, each month written whole, replacing it), then top up
  from the API where the files end. Deployed as `v1-backfill-usgs-streamflow`, run by hand: for
  a rebuild, or to reload months USGS has since approved.
- `flows/ingest_nwm.py`: ingest NWM operational streamflow (`channel_rt`, from NOAA's GCS bucket)
  at the gages' reaches, one dataset per configuration with legacy's names (`nwm31_short_range`,
  `nwm31_medium_range` for `medium_range_mem1`, ...), sharing one series table. Reaches are the
  `usgs_nwm31` crosswalk's for the gages in the configuration's domain (their `state_name`, as
  legacy). Deployed as `v1-ingest-nwm-<configuration>` (twice daily on legacy's times, each run from the dataset's latest cycle).
- `tests/smoke_derived.py`: the flow against a throwaway local catalog, in the image.
- `tests/smoke_evaluations.py`: the run-evaluations flow against a fake control plane.
- `tests/smoke_ingest_usgs.py`: the USGS ingest flow against a throwaway local catalog and a fake API.
- `tests/smoke_ingest_nwm.py`: the NWM ingest flow against a throwaway local catalog and a fake GCS.

## Credentials

The client's secret is `automation-client-secret` in `control-plane-secrets` (remote: in
`REMOTE_SECRETS`). The Keycloak bootstrap sets it on the client, and `load-secrets` copies it
into the Prefect Secret block `teehr-platform-automation-secret`, which the flows load (so it
isn't in the deployments' job variables). After changing it, redeploy both. Its write membership is the control plane's `SYSTEM_PROJECT_WRITERS`, restored on
every restart.

The image's teehr-core commit is `teehrCoreVersion` in `project.garden.yml` (a var change
needs `garden deploy prefect-v1-workflow-deploy --force`).
