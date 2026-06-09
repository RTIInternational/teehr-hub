import { Form } from "react-bootstrap";

const NULL_OPTION = "__NULL__";

export const FilterSidebar = ({
  state,
  mapFilters,
  updateMapFilters,
  loadLocations,
}) => {
  const handleMapFilterChange = async (filterType, value) => {
    const newFilters = { ...mapFilters, [filterType]: value };
    updateMapFilters({ [filterType]: value });

    // Reload locations when base metrics change
    const reloadFilters = new Set([
      "configuration",
      "variable",
      "threshold",
      "aggMethod",
      "leadTimeBin",
    ]);
    if (reloadFilters.has(filterType)) {
      await loadLocations({
        configuration: newFilters.configuration,
        variable: newFilters.variable,
        threshold: newFilters.threshold,
        aggMethod: newFilters.aggMethod,
        leadTimeBin: newFilters.leadTimeBin,
      });
    }
  };

  return (
    <div className="p-3">
      {/* Configuration Filter */}
      <Form.Group className="mb-3">
        <Form.Label className="small fw-bold">Model Configuration</Form.Label>
        <Form.Select
          size="sm"
          value={mapFilters.configuration || ""}
          onChange={(e) =>
            handleMapFilterChange("configuration", e.target.value || null)
          }
        >
          <option value="">Select Configuration...</option>
          {Array.isArray(state.configurations) &&
            state.configurations.map((config) => (
              <option key={config} value={config}>
                {config}
              </option>
            ))}
        </Form.Select>
      </Form.Group>

      {/* Threshold Filter */}
      <Form.Group className="mb-3">
        <Form.Label className="small fw-bold">Threshold</Form.Label>
        <Form.Select
          size="sm"
          value={
            mapFilters.threshold === null
              ? NULL_OPTION
              : (mapFilters.threshold ?? "")
          }
          onChange={(e) =>
            handleMapFilterChange(
              "threshold",
              e.target.value === NULL_OPTION ? null : e.target.value || null,
            )
          }
        >
          <option value="">Select Threshold...</option>
          {Array.isArray(state.thresholds) &&
            state.thresholds.map((threshold) => {
              const optionValue = threshold === null ? NULL_OPTION : threshold;
              const optionLabel = threshold === null ? "None" : threshold;
              return (
                <option key={String(optionValue)} value={optionValue}>
                  {optionLabel}
                </option>
              );
            })}
        </Form.Select>
      </Form.Group>

      {/* Metric Filter */}
      <Form.Group className="mb-3">
        <Form.Label className="small fw-bold">Metric</Form.Label>
        <Form.Select
          size="sm"
          value={mapFilters.metricName || ""}
          onChange={(e) => {
            handleMapFilterChange("metricName", e.target.value || null);
          }}
        >
          <option value="">Select Metric...</option>
          {(() => {
            // Try to find metrics from any available table in the batch response
            // This works for both single-table and multi-table dashboards
            const allTableProps = state.tableProperties || {};
            const allMetrics = [];

            // Collect all unique metrics from all tables
            Object.values(allTableProps).forEach((tableProps) => {
              if (Array.isArray(tableProps?.metrics)) {
                tableProps.metrics.forEach((metric) => {
                  if (!allMetrics.includes(metric)) {
                    allMetrics.push(metric);
                  }
                });
              }
            });

            return allMetrics.map((metricName) => (
              <option key={metricName} value={metricName}>
                {metricName}
              </option>
            ));
          })()}
        </Form.Select>
      </Form.Group>

      {/* Aggregation Method Filter */}
      <Form.Group className="mb-3">
        <Form.Label className="small fw-bold">
          Streamflow aggregation method
        </Form.Label>
        <Form.Select
          size="sm"
          value={mapFilters.aggMethod || ""}
          onChange={(e) =>
            handleMapFilterChange("aggMethod", e.target.value || null)
          }
        >
          <option value="">Select Aggregation Method...</option>
          {Array.isArray(state.aggMethods) &&
            state.aggMethods.map((aggMethod) => (
              <option key={aggMethod} value={aggMethod}>
                {aggMethod}
              </option>
            ))}
        </Form.Select>
      </Form.Group>

      {/* Forecast Lead Time Bin Filter */}
      <Form.Group className="mb-3">
        <Form.Label className="small fw-bold">Lead time (hours): </Form.Label>
        <Form.Select
          size="sm"
          value={mapFilters.leadTimeBin || ""}
          onChange={(e) =>
            handleMapFilterChange("leadTimeBin", e.target.value || null)
          }
        >
          <option value="">Select Lead Time Bin...</option>
          {Array.isArray(state.leadTimeBins) &&
            state.leadTimeBins.map((config) => (
              <option key={config} value={config}>
                {config}
              </option>
            ))}
        </Form.Select>
      </Form.Group>
    </div>
  );
};
