ALTER TABLE primary_timeseries SET TBLPROPERTIES (
    'write.parquet.row-group-size-bytes' = '8388608'
)

ALTER TABLE secondary_timeseries SET TBLPROPERTIES (
    'write.parquet.row-group-size-bytes' = '8388608'
)
