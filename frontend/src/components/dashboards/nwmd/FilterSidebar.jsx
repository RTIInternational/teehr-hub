import { Form } from "react-bootstrap";

export const FilterSidebar = ({
  state,
  mapFilters,
  updateMapFilters,
  loadLocations,
}) => {
  const handleMapFilterChange = async (filterType, value) => {
    const newFilters = { ...mapFilters, [filterType]: value };
    updateMapFilters({ [filterType]: value });

    // Reload locations when configuration or variable changes
    // if (filterType === "configuration" || filterType === "variable") {
    await loadLocations({
      configuration: newFilters.configuration,
      variable: newFilters.variable,
      threshold: newFilters.threshold,
      aggMethod: newFilters.aggMethod,
      leadTimeBin: newFilters.leadTimeBin,
    });
    // }
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
          value={mapFilters.threshold || ""}
          onChange={(e) =>
            handleMapFilterChange("threshold", e.target.value || null)
          }
        >
          <option value="">Select Threshold...</option>
          {Array.isArray(state.thresholds) &&
            state.thresholds.map((threshold) => (
              <option key={threshold} value={threshold}>
                {threshold}
              </option>
            ))}
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