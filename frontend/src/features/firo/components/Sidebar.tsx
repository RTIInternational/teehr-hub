import Form from 'react-bootstrap/Form';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';

import { useDistinctValues } from '@/shared/queries/distinctValues';

import { useFiroActions, useFiroDashboardStore } from '../store';
import { formatConfigurationName } from '../utils/formatConfigurationName';

import './Sidebar.css';

const ANALYSIS_PAGES = [
  {
    key: 'deterministic',
    label: 'Deterministic Analysis',
    path: '/firo/detailed-analysis/deterministic',
  },
  {
    key: 'full-distribution',
    label: 'Full Distribution Metrics',
    path: '/firo/detailed-analysis/full-distribution',
  },
  {
    key: 'event-thresholds',
    label: 'Event Threshold Metrics',
    path: '/firo/detailed-analysis/event-thresholds',
  },
];

const METRICS_TABLE = 'locations_metrics';

// ─── Shared button shape ───────────────────────────────────────────────────────
// active   → blue fill, white text
// idle     → transparent, dark text, grey hover (via CSS class)
// disabled → transparent bg, outlined border, muted text, no hover

type NavButtonProps = {
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
};

const NavButton = ({ label, active = false, disabled = false, onClick }: NavButtonProps) => (
  <button
    onClick={onClick}
    disabled={disabled}
    aria-current={active ? 'page' : undefined}
    className={`firo-nav-btn ${
      active ? 'sidebar-btn--active' : disabled ? 'sidebar-btn--disabled' : 'sidebar-btn--idle'
    }`}
    style={{
      textDecoration: 'none',
      cursor: disabled ? 'not-allowed' : 'pointer',
    }}
  >
    {label}
  </button>
);

export const Sidebar = () => {
  const selectedLocation = useFiroDashboardStore((s) => s.selectedLocation);
  const selectedConfigurationName = useFiroDashboardStore((s) => s.selectedConfigurationName);
  const selectedVariableName = useFiroDashboardStore((s) => s.selectedVariableName);
  const { setConfigurationName, setVariableName } = useFiroActions();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const configurationsQuery = useDistinctValues(METRICS_TABLE, 'configuration_name');
  const variablesQuery = useDistinctValues(METRICS_TABLE, 'variable_name');

  const configurationOptions = (configurationsQuery.data ?? []).filter(
    (value) => value !== null && value !== 'null' && value !== 'None'
  );
  const variableOptions = (variablesQuery.data ?? []).filter(
    (value) => value !== null && value !== 'null' && value !== 'None'
  );

  const configurationValue =
    configurationOptions.includes(selectedConfigurationName) || configurationOptions.length === 0
      ? selectedConfigurationName
      : configurationOptions[0];

  const variableValue =
    variableOptions.includes(selectedVariableName) || variableOptions.length === 0
      ? selectedVariableName
      : variableOptions[0];

  const analysisDisabled = selectedLocation === null;

  return (
    <div className="firo-sidebar d-flex flex-column">
      <div className="firo-sidebar-section">
        <span className="firo-sidebar-label">Configuration</span>

        <div className="mt-2 d-flex flex-column gap-2">
          <Form.Group controlId="firo-sidebar-model">
            <Form.Label className="firo-sidebar-field-label mb-1">Model</Form.Label>
            <Form.Select
              size="sm"
              className="firo-sidebar-select"
              value={configurationValue}
              onChange={(e) => setConfigurationName(e.target.value)}
              disabled={configurationsQuery.isLoading || configurationOptions.length === 0}
            >
              {configurationOptions.map((value) => (
                <option key={value} value={value}>
                  {formatConfigurationName(value)}
                </option>
              ))}
            </Form.Select>
          </Form.Group>

          <Form.Group controlId="firo-sidebar-variable">
            <Form.Label className="firo-sidebar-field-label mb-1">Variable</Form.Label>
            <Form.Select
              size="sm"
              className="firo-sidebar-select"
              value={variableValue}
              onChange={(e) => setVariableName(e.target.value)}
              disabled={variablesQuery.isLoading || variableOptions.length === 0}
            >
              {variableOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Form.Select>
          </Form.Group>
        </div>
      </div>

      {/* Header */}
      <div className="firo-sidebar-section">
        <span className="firo-sidebar-label">Workflow</span>

        <div className="mt-2 d-flex flex-column gap-1">
          {/* 1 — Location Selection */}
          <NavButton
            label="Location Selection"
            active={pathname.startsWith('/firo/location-selection')}
            onClick={() => navigate('/firo/location-selection')}
          />

          {/* Sub-heading — Detailed Location Analysis */}
          <div
            className={`d-flex align-items-center px-1 mt-2 firo-subheading ${analysisDisabled ? 'is-disabled' : ''}`}
          >
            <span className="firo-subheading-label">Detailed Location Analysis</span>
          </div>

          {/* Analysis sub-pages — indented by wrapping in a left-padded container */}
          <div className="firo-nav-indent">
            <div className="d-flex flex-column gap-1">
              {ANALYSIS_PAGES.map((page) =>
                analysisDisabled ? (
                  <NavButton key={page.key} label={page.label} disabled />
                ) : (
                  <NavLink
                    key={page.key}
                    to={page.path}
                    className={({ isActive }) =>
                      `firo-nav-btn ${isActive ? 'sidebar-btn--active' : 'sidebar-btn--idle'}`
                    }
                    style={({ isActive }) => ({
                      textDecoration: 'none',
                      fontWeight: isActive ? 600 : 400,
                    })}
                  >
                    {page.label}
                  </NavLink>
                )
              )}
            </div>
          </div>

          <div className="mt-1" />

          {/* 2 — Top Events */}
          <NavButton
            label="Top Events Performance Analysis"
            active={pathname.startsWith('/firo/top-events')}
            disabled={analysisDisabled}
            onClick={() => navigate('/firo/top-events')}
          />
        </div>
      </div>

      {/* Selected location summary */}
      {selectedLocation && (
        <div className="firo-location-summary">
          <p className="firo-location-summary-title">Selected Location</p>
          <p
            className="small fw-semibold firo-location-summary-name text-truncate"
            title={selectedLocation.name}
          >
            {selectedLocation.name}
          </p>
          <p className="firo-location-summary-id">{selectedLocation.primary_location_id}</p>
        </div>
      )}
    </div>
  );
};
