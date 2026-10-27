# Migration 0012: Drop `grid_pixel_coverage_weights`

Migrations manage core tables only. The weights flow (`prefect-workflows/workflows/ingests/pixel_coverage_weights.py`)
owns this table and creates it when it's missing, like the other workflow-owned tables (see [0011](../0011)).
[0007](../0007) and [0008](../0008) should not have touched it. This migration hands it back to the flow, and no later
migration should change it.

The flow's schema replaces `domain_name` with `grid_name`, drops `variable_name` and `position_index`, and is
partitioned by `grid_name`. The existing rows can't be kept:

- The Sedona rows are 1-based and north-up, while the flow's are 0-based and south-up on the NWM grids. Both are
  tagged `nwm30_conus_forcing`, so they would mix.
- Rows from the old Icechunk flow predate the polygon repair and coverage filter.

Checked 2026-10-24: the remote table held only NWM 3.0 weights (CONUS, Alaska, Hawaii, Puerto Rico). Sampled CONUS
rows, converted to teehr's convention (row = 3840 − row, col = col − 1), matched fresh teehr weights, so they were
correct, just indexed differently.

After applying, run the `calculate-pixel-coverage-weights-icechunk` deployment before any mean areal values run.

The `nwm30_retrospective` weights are also in
`s3://ciroh-rti-public-data/teehr-data-warehouse/common/map_weights/nwm30_retrospective_conus_usgs_basins/`. The MAP
and MAT computed from them stay in the timeseries tables.
