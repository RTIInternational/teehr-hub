UPDATE variables
SET name = 'rainfall_hourly_mean',
    long_name = 'Hourly Mean Rainfall Rate'
WHERE name = 'rainfall_hourly_rate'

UPDATE variables
SET long_name = '6-Hour Instantaneous Streamflow',
WHERE name = 'streamflow_6hr_inst'