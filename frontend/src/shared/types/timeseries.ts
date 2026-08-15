import type { MapLocation } from './locations';

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

type TimeseriesPoint = {
  value_time: string;
  value: number;
};

export type TimeseriesRequestFilters = {
  primary_location_id: string;
} & TimeseriesFilters;

export type TimeseriesResponse = Timeseries[];

export type TimeseriesState = {
  selectedLocation: MapLocation | null;
  timeseriesFilters: TimeseriesFilters;
};
