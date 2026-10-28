// Empty datasets means the map's active dataset; null dates mean up to 3 years before the map's date
export type GriddedTimeseriesFilters = {
  datasets: string[];
  start_date: string | null;
  end_date: string | null;
};
