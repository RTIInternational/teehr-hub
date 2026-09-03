import { Form } from 'react-bootstrap';

import { useConfigurations } from '@/shared/queries/configurations';
import { useDistinctValues } from '@/shared/queries/distinctValues';

import { useTableProperties } from '../../../shared/queries/queryables';
import LeadTimeRangeFilter from './LeadTimeRangeFilter';
import { isNwmdMetric } from './utils';

const NULL_OPTION = '__NULL__';
const ALT_HYPOTHESIS_OPTIONS = [
  { value: '=0', label: 'Metric = 0' },
  { value: '!=0', label: 'Metric != 0' },
  { value: '>1', label: 'Metric > 1' },
  { value: '<1', label: 'Metric < 1' },
  { value: '>0', label: 'Metric > 0' },
  { value: '<0', label: 'Metric < 0' },
];

export const FilterSidebar = ({ tables, mapFilters, updateMapFilters }) => {
  const tableProperties = useTableProperties(tables);

  // Queryable values
  const quarters = useDistinctValues(tables[0], 'quarter');
  const configurations = useConfigurations(tables[0]);
  const thresholds = useDistinctValues(tables[0], 'threshold');
  const aggMethods = useDistinctValues(tables[0], 'window_agg');
  const leadTimeBins = useDistinctValues(tables[0], 'forecast_lead_time_bin');

  const handleMapFilterChange = async (filterType, value) => {
    // Reset alt hypothesis when the metric changes — the operator is metric-specific
    const extraUpdates = filterType === 'metricName' ? { altHypothesis95: null } : {};
    updateMapFilters({ [filterType]: value, ...extraUpdates });
  };

  return (
    <div className="p-3">
      {/* Quarter Filter */}
      <Form.Group className="mb-3">
        <Form.Label className="small fw-bold">Quarter</Form.Label>
        <Form.Select
          size="sm"
          value={mapFilters.quarter || ''}
          onChange={(e) => handleMapFilterChange('quarter', e.target.value || null)}
        >
          {Array.isArray(quarters.data) &&
            quarters.data.map((quarter) => (
              <option key={quarter} value={quarter}>
                {quarter}
              </option>
            ))}
        </Form.Select>
      </Form.Group>

      {/* Configuration Filter */}
      <Form.Group className="mb-3">
        <Form.Label className="small fw-bold">Model Configuration</Form.Label>
        <Form.Select
          size="sm"
          value={mapFilters.configuration || ''}
          onChange={(e) => handleMapFilterChange('configuration', e.target.value || null)}
        >
          {Array.isArray(configurations.data) &&
            configurations.data.map((config) => (
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
          value={mapFilters.threshold === null ? NULL_OPTION : (mapFilters.threshold ?? '')}
          onChange={(e) =>
            handleMapFilterChange(
              'threshold',
              e.target.value === NULL_OPTION ? null : e.target.value || null
            )
          }
        >
          {Array.isArray(thresholds.data) &&
            thresholds.data
              .toSorted((a, b) => {
                if (a === null) return -1;
                if (b === null) return 1;
                return a.localeCompare(b);
              })
              .map((threshold) => {
                const optionValue = threshold === null ? NULL_OPTION : threshold;
                const optionLabel = threshold === null ? 'None' : threshold;
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
          value={mapFilters.metricName || ''}
          onChange={(e) => {
            const selectedMetric = e.target.value;
            handleMapFilterChange(
              'metricName',
              selectedMetric && isNwmdMetric(selectedMetric) ? selectedMetric : null
            );
          }}
        >
          {(() => {
            // Try to find metrics from any available table in the batch response
            // This works for both single-table and multi-table dashboards
            const allTableProps = tableProperties.data || {};
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

            return allMetrics.filter(isNwmdMetric).map((metricName) => (
              <option key={metricName} value={metricName}>
                {metricName}
              </option>
            ));
          })()}
        </Form.Select>
      </Form.Group>

      {/* Aggregation Method Filter */}
      <Form.Group className="mb-3">
        <Form.Label className="small fw-bold">Streamflow aggregation method</Form.Label>
        <Form.Select
          size="sm"
          value={mapFilters.aggMethod || ''}
          onChange={(e) => handleMapFilterChange('aggMethod', e.target.value || null)}
        >
          {Array.isArray(aggMethods.data) &&
            aggMethods.data.map((aggMethod) => (
              <option key={aggMethod} value={aggMethod}>
                {aggMethod}
              </option>
            ))}
        </Form.Select>
      </Form.Group>

      {/* Forecast Lead Time Bin Filter */}
      <Form.Group className="mb-3">
        <LeadTimeRangeFilter
          leadTimeBins={leadTimeBins.data}
          selectedLeadTimeBin={mapFilters.leadTimeBin}
          onCommit={(nextBin) => handleMapFilterChange('leadTimeBin', nextBin)}
        />
      </Form.Group>

      {/* Alt Hypothesis Filter */}
      <Form.Group className="mb-3">
        <Form.Label className="small fw-bold">Alt. Hypothesis (95% confidence)</Form.Label>
        <Form.Select
          size="sm"
          value={mapFilters.altHypothesis95 || ''}
          onChange={(e) => handleMapFilterChange('altHypothesis95', e.target.value || null)}
        >
          <option value="">None</option>
          {ALT_HYPOTHESIS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Form.Select>
      </Form.Group>
    </div>
  );
};
