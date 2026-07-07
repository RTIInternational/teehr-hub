import { Form } from "react-bootstrap";

export const CdfSidebar = ({ state, plotIds, setCdfPlotMetric }) => {
  return (
    <div className="p-3">
      {plotIds.map((plotId) => (
        <Form.Group key={plotId} className="mb-3">
          <Form.Label className="small fw-bold">{plotId}</Form.Label>
          <Form.Select
            size="sm"
            value={state.cdfPlots?.[plotId]?.metricName}
            onChange={(e) => {
              setCdfPlotMetric(plotId, e.target.value);
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
      ))}
    </div>
  );
};
