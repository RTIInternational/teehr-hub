ALTER TABLE primary_timeseries ADD PARTITION FIELD configuration_name

ALTER TABLE primary_timeseries SET TBLPROPERTIES (
    'write.distribution-mode' = 'range',
    'write.sort-order' = 'location_id ASC NULLS LAST, value_time ASC NULLS LAST',
    'write.target-file-size-bytes' = '536870912'
)

ALTER TABLE secondary_timeseries ADD PARTITION FIELD configuration_name

ALTER TABLE secondary_timeseries SET TBLPROPERTIES (
    'write.distribution-mode' = 'range',
    'write.sort-order' = ' location_id ASC NULLS LAST, reference_time ASC NULLS LAST, value_time ASC NULLS LAST',
    'write.target-file-size-bytes' = '536870912'
)
