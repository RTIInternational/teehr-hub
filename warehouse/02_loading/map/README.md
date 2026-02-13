## Mean Areal Precip (MAP) for NWM v3.0 Retrospective/USGS Basins
### Inputs
- NWM v3.0 retrospective RAINRATE: https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com/index.html#CONUS/netcdf/FORCING/
    - Hourly timestep
    - 1979-02-01 00:00 to 2023-01-31 23:00
- USGS high-res drainage basins. TEEHR-Hub data drive: `/data/common/geometry/usgsbasin_geometry_highres.all.parquet`
    - 9068 locations (basin polygons)
 
### Output Summary
- configuration_name: `nwm30_retrospective`
- location ID prefix: `usgsbasin`
- unit_name: `mm/s`
- variable_name: `rainfall_hourly_rate`
- number of values per location: 385704
- summary stats:

| stat | value |
|---|---|
|count | 3497563872 |
|mean | 3.259294532435737E-5 |
|stddev | 1.6932488604435412E-4 |
|min | 0.0 |
|max | 0.11853919 |

### Processing Steps
#### Calculate fractional area coverage (weights) of pixels overlapping polygons
- Notebook: https://github.com/RTIInternational/teehr-hub/blob/main/warehouse/03_preprocessing/map/01_calculate_nwm30_pixel_weights.ipynb
- Values in s3 at: s3://ciroh-rti-public-data/teehr-data-warehouse/common/map_weights/nwm30_retrospective_conus_usgs_basins/

#### Calculate MAP values 
- Notebook: https://github.com/RTIInternational/teehr-hub/blob/main/warehouse/03_preprocessing/map/02_calculate_nwm30_retro_usgs_map.ipynb
- Values in s3 at: s3://ciroh-rti-public-data/teehr-data-warehouse/common/map_values/nwm30_retrospective_conus_usgs_basins/

### Loading to the Warehouse
- Basin locations: https://github.com/RTIInternational/teehr-hub/blob/main/warehouse/02_loading/04_load_usgs_basin_locations.ipynb
- MAP values: https://github.com/RTIInternational/teehr-hub/blob/main/warehouse/02_loading/05_load_nwm30_map_values.ipynb

### Contact
- slamont@rti.org
- mdenno@rti.org

### Publish Date
- 2026-02-26