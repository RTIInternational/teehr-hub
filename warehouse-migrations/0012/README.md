# Migration 0012: Drop `grid_pixel_coverage_weights` for the Icechunk weights schema

The pixel coverage weights flow (`prefect-workflows/workflows/ingests/pixel_coverage_weights.py`) now writes:

```
fraction_covered, row, col, location_id, configuration_name, grid_name, created_at, updated_at
PARTITIONED BY (grid_name), unique on (location_id, row, col, grid_name)
```

The table from [0007](../0007) has `domain_name` (now `grid_name`), `variable_name` (weights are geometry only, shared
by every variable on a grid) and `position_index` (only the removed Sedona MAP flow used it).

The table is dropped rather than altered, because its rows can't be kept as they are:

- **Sedona rows use a different pixel index.** The `02_loading/map/01_calculate_nwm30_pixel_weights.ipynb` rows are
  1-based and north-up (`RS_PixelAsPolygons`). The Icechunk flow uses teehr's 0-based rows, which run south-up on the
  NWM grids. That notebook also re-tagged every existing row as `nwm30_conus_forcing`, the same grid the Icechunk
  rows use. The old flow kept the two sets apart by `variable_name`, but the new one reads by `grid_name` only, so it
  would mix them.
- **Any rows from the old Icechunk weights flow predate the polygon repair and coverage filter.** The new flow drops
  invalid or mostly off-grid polygons, so its weights differ from these anyway.

Checked 2026-10-24 against the remote table, which held only these NWM 3.0 sets: `nwm30_conus_forcing` (10,354
basins), `nwm30_alaska_forcing`, `nwm30_hawaii_forcing` and `nwm30_puertorico_forcing`. For 25 sampled CONUS basins,
the rows converted to teehr's convention (row = 3840 − row, col = col − 1) matched freshly computed teehr weights on
every pixel, to float32 precision. So the CONUS weights were correct, just indexed differently. The Alaska, Hawaii and
Puerto Rico weights come back when those domains get Icechunk repos and weights runs.

The weights flow recreates the table, with the schema and partitioning above, on its next run. Run the
`calculate-pixel-coverage-weights-icechunk` deployment after applying this migration, before any mean areal values
run. A fresh warehouse runs `0007` and then this migration, and ends the same way.

The Sedona-era `nwm30_retrospective` weights are also in
`s3://ciroh-rti-public-data/teehr-data-warehouse/common/map_weights/nwm30_retrospective_conus_usgs_basins/`
(see `warehouse/remote/02_loading/map/README.md`). The MAP and MAT values computed from them stay in the timeseries
tables.
