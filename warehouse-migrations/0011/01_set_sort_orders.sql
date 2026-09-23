ALTER TABLE primary_timeseries WRITE ORDERED BY location_id ASC NULLS LAST, value_time ASC NULLS LAST

ALTER TABLE secondary_timeseries WRITE ORDERED BY location_id ASC NULLS LAST, reference_time ASC NULLS LAST, value_time ASC NULLS LAST
