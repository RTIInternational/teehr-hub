import { useState } from 'react';
import { Dropdown, Form } from 'react-bootstrap';
import { useConfigurations } from '@/shared/queries/configurations';
import { useTableProperties } from '@/shared/queries/queryables';
import { useVariables } from '@/shared/queries/variables';
import type { MapFilters } from '@/shared/types/maps';

type MapFilterButtonProps = {
  tables: string[];
  mapFilters: MapFilters;
  updateMapFilters: (filter: { [filter: string]: unknown }) => void;
};

const MapFilterButton = ({ tables, mapFilters, updateMapFilters }: MapFilterButtonProps) => {
  const [showDropdown, setShowDropdown] = useState(false);

  const configurations = useConfigurations(tables[0]);
  const variables = useVariables(tables[0]);
  const tableProperties = useTableProperties(tables);

  const handleMapFilterChange = async (filterType: string, value: unknown) => {
    updateMapFilters({ [filterType]: value });
  };

  return (
    <div className="position-absolute top-0 end-0 m-3" style={{ zIndex: 1000 }}>
      <Dropdown show={showDropdown} onToggle={setShowDropdown}>
        <Dropdown.Toggle variant="light" className="shadow-sm">
          🗺️ Map Display Settings
        </Dropdown.Toggle>

        <Dropdown.Menu style={{ minWidth: '300px' }}>
          <div className="p-3">
            {/* Configuration Filter */}
            <Form.Group className="mb-3">
              <Form.Label className="small fw-bold">Configuration</Form.Label>
              <Form.Select
                size="sm"
                value={mapFilters.configuration || ''}
                onChange={(e) => handleMapFilterChange('configuration', e.target.value || null)}
              >
                <option value="">Select Configuration...</option>
                {Array.isArray(configurations.data) &&
                  configurations.data.map((config) => (
                    <option key={config} value={config}>
                      {config}
                    </option>
                  ))}
              </Form.Select>
            </Form.Group>

            {/* Variable Filter */}
            <Form.Group className="mb-3">
              <Form.Label className="small fw-bold">Variable</Form.Label>
              <Form.Select
                size="sm"
                value={mapFilters.variable || ''}
                onChange={(e) => handleMapFilterChange('variable', e.target.value || null)}
              >
                <option value="">Select Variable...</option>
                {Array.isArray(variables.data) &&
                  variables.data.map((variable) => (
                    <option key={variable} value={variable}>
                      {variable}
                    </option>
                  ))}
              </Form.Select>
            </Form.Group>

            {/* Metric Filter */}
            <Form.Group className="mb-0">
              <Form.Label className="small fw-bold">Color By Metric</Form.Label>
              <Form.Select
                size="sm"
                value={mapFilters.metricName || ''}
                onChange={(e) => handleMapFilterChange('metricName', e.target.value || null)}
              >
                <option value="">Select Metric...</option>
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

                  return allMetrics.map((metricName) => (
                    <option key={metricName} value={metricName}>
                      {metricName}
                    </option>
                  ));
                })()}
              </Form.Select>
            </Form.Group>
          </div>
        </Dropdown.Menu>
      </Dropdown>
    </div>
  );
};

export default MapFilterButton;
