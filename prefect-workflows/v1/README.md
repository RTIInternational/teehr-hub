# v1 Prefect flows

Flows for the v1 warehouse (ADR-0019 in teehr-cloud-core), apart from the legacy flows: their
own image (`Dockerfile`: teehr-core's warehouse writer and builders, Prefect; no legacy
`teehr`, Spark or JVM), deployer job and deployments (`prefect-local.yaml`,
`prefect-remote.yaml`), on the shared `kubernetes-pool`. They act as `prefect-polaris`, whose
`teehr-platform-write` role writes `public`.

- `flows/derived.py`: build a derived dataset (percentiles, climatology, naive scale) of an
  observed timeseries. Register the dataset first:
  `teehr datasets create usgs_streamflow_percentiles -p public --kind percentiles --observed usgs_streamflow`.
- `tests/smoke_derived.py`: the flow against a throwaway local catalog, in the image.

The image's teehr-core commit is `teehrCoreVersion` in `project.garden.yml` (a var change
needs `garden deploy prefect-v1-workflow-deploy --force`).
