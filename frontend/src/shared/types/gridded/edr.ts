export type TimeseriesData = {
  times: string[];
  // null where a step has no data
  values: (number | null)[];
};

// One dataset's part of a point query: data, an error, or why it was skipped
export type DatasetTimeseries = {
  datasetId: string;
  variable: string | null;
  data?: TimeseriesData;
  error?: string;
  skipped?: string;
  isLoading: boolean;
};
