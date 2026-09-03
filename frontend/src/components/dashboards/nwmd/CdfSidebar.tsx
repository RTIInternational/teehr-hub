import { Form } from 'react-bootstrap';

import { useDashboard } from '@/context/NwmdDashboardContext';

import { useTableProperties } from '../../../shared/queries/queryables';
import { useCdfPlots } from './useCdfPlots';
import { isNwmdMetric } from './utils';

type CdfSidebarProps = {
  tables: string[];
};

export const CdfSidebar = ({ tables }: CdfSidebarProps) => {
  const { state } = useDashboard();
  const { plotIds, setCdfPlotMetric } = useCdfPlots();
  const tableProperties = useTableProperties(tables);

  return (
    <div className="p-3">
      {plotIds.map((plotId: string) => (
        <Form.Group key={plotId} className="mb-3">
          <Form.Label className="small fw-bold">{plotId}</Form.Label>
          <Form.Select
            size="sm"
            value={state.cdfPlots?.[plotId]?.metricName}
            onChange={(e) => {
              const selectedMetric = e.target.value;
              if (isNwmdMetric(selectedMetric)) {
                setCdfPlotMetric(plotId, selectedMetric);
              }
            }}
          >
            {(() => {
              // Try to find metrics from any available table in the batch response
              // This works for both single-table and multi-table dashboards
              const allTableProps = tableProperties.data || {};
              const allMetrics: string[] = [];

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

              return allMetrics.filter(isNwmdMetric).map((metricName) => (
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
