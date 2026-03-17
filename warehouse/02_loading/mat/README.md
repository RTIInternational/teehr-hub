## Mean Areal Temperature (MAT) for NWM v3.0 Retrospective/USGS Basins
### Inputs
- NWM v3.0 retrospective T2D: https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com/index.html#CONUS/netcdf/FORCING/
    - Hourly timestep
    - 1979-02-01 00:00 to 2023-01-31 23:00
- USGS high-res drainage basins. TEEHR-Hub data drive: `/data/common/geometry/usgsbasin_geometry_highres.all.parquet`
    - 9068 locations (basin polygons)
 
### Output Summary
- configuration_name: `nwm30_retrospective`
- location ID prefix: `usgsbasin`
- unit_name: `K`
- variable_name: `temperature_hourly_mean`
- number of values per location: 385704
- summary stats:

| stat | value |
|---|---|
|count | 3497563872 |
|mean | 283.62 |
|stddev | 11.36 |
|min | 227.92 |
|max | 321.43 |

### Processing Steps
#### Calculate fractional area coverage (weights) of pixels overlapping polygons
- Notebook: https://github.com/RTIInternational/teehr-hub/blob/main/warehouse/02_loading/mat/01_calculate_nwm30_pixel_weights.ipynb
- Values in s3 at: s3://ciroh-rti-public-data/teehr-data-warehouse/common/map_weights/nwm30_retrospective_conus_usgs_basins/

#### Calculate MAT values 
- Notebook: https://github.com/RTIInternational/teehr-hub/blob/main/warehouse/02_loading/mat/calculate_nwm30_retro_usgs_mat.ipynb
- Values in s3 at: s3://ciroh-rti-public-data/teehr-data-warehouse/common/mat_values/nwm30_retrospective_conus_usgs_basins/

### Loading to the Warehouse
- Basin locations: https://github.com/RTIInternational/teehr-hub/blob/main/warehouse/02_loading/04_load_usgs_basin_locations.ipynb
- MAT values: https://github.com/RTIInternational/teehr-hub/blob/main/warehouse/02_loading/06_load_nwm30_mat_values.ipynb

### Contact
- slamont@rti.org
- mdenno@rti.org

### Publish Date
- 2026-03-17