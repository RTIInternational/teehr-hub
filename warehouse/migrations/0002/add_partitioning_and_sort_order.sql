ALTER TABLE primary_timeseries ADD PARTITION FIELD months(value_time)

ALTER TABLE primary_timeseries SET TBLPROPERTIES (
    'write.distribution-mode' = 'range',
    'write.sort-order' = 'value_time ASC NULLS LAST, location_id ASC NULLS LAST'
)

ALTER TABLE secondary_timeseries ADD PARTITION FIELD months(value_time)

ALTER TABLE secondary_timeseries SET TBLPROPERTIES (
    'write.distribution-mode' = 'range',
    'write.sort-order' = 'value_time ASC NULLS LAST, reference_time ASC NULLS LAST, location_id ASC NULLS LAST'
)
