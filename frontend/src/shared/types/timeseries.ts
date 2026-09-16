import type { MapLocation } from './locations';
import type { OgcResponse } from './ogc';

export type PrimaryTimeseriesRequestFilters = {
  start_date?: string;
  end_date?: string;
  variable?: string | string[];
  configuration?: string | string[];
  duration?: string;
  limit?: number;
};

export type SecondaryTimeseriesRequestFilters = PrimaryTimeseriesRequestFilters & {
  reference_start_date?: string;
  reference_end_date?: string;
};

export type Timeseries = {
  series_type: 'primary' | 'secondary';
  primary_location_id: string;
  secondary_location_id?: string;
  reference_time: string | null;
  configuration_name: string;
  variable_name: string;
  unit_name: string;
  member?: string | null;
  timeseries: TimeseriesPoint[];
  duration_token?: string | null;
};

export type TimeseriesFilters = {
  primary: {
    variables: string[];
    start_date: string;
    end_date: string;
    duration: string;
  };
  secondary: {
    configurations: string[];
    variables: string[];
    start_date?: string;
    end_date?: string;
    reference_start_date?: string;
    reference_end_date?: string;
  };
};

export type TimeseriesItem = {
  series_type: string;
  primary_location_id: string;
  secondary_location_id?: string;
  member?: string;
  reference_time: null;
  configuration_name: string;
  variable_name: string;
  unit_name: string;
  value_time: string;
  value: number;
  created_at: string;
  updated_at: string;
};

type TimeseriesPoint = {
  value_time: string;
  value: number;
};

export type TimeseriesRequestFilters = {
  primary_location_id?: string;
} & TimeseriesFilters;

export type TimeseriesResponse = OgcResponse<TimeseriesItem>;

export type TimeseriesResult = Timeseries[];

export type TimeseriesState = {
  selectedLocation: MapLocation | null;
  timeseriesFilters: TimeseriesFilters;
};
