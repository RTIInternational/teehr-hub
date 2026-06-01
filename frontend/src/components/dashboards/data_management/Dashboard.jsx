/**
 * Data Management Dashboard
 *
 * Three tabs:
 *  1. Configurations Summary  — map + configs_summary table
 *  2. Locations Summary       — map + locations_with_attributes table
 *  3. Configuration Completeness — map with polygon overlay + completeness heatmap
 *
 * All tab contents are lazy-mounted (on first visit) and kept mounted thereafter
 * so that map state is preserved across tab switches.
 */
import { useState } from 'react';
import { useDataDashboard, ActionTypes } from '../../../context/DataDashboardContext.jsx';
import ConfigurationsSummaryTab from './ConfigurationsSummaryTab';
import LocationsSummaryTab from './LocationsSummaryTab';
import CompletenessTab from './CompletenessTab';

const TABS = [
  { id: 'configurations', label: 'Configurations Summary' },
  { id: 'locations',      label: 'Locations Summary' },
  { id: 'completeness',   label: 'Configuration Completeness' },
];

const Dashboard = () => {
  const { state, dispatch } = useDataDashboard();
  const [activeTab, setActiveTab] = useState('configurations');
  // Track which tabs have ever been activated so we lazy-mount them
  const [visitedTabs, setVisitedTabs] = useState(new Set(['configurations']));

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    setVisitedTabs((prev) => new Set([...prev, tabId]));
  };

  return (
    <div
      className="d-flex flex-column"
      style={{ height: 'calc(100dvh - 56px)', overflow: 'hidden', padding: '12px', gap: '8px' }}
    >
      {/* Global error alert */}
      {state.error && (
        <div
          className="alert alert-danger alert-dismissible"
          role="alert"
          style={{ flex: '0 0 auto', margin: 0, zIndex: 1000 }}
        >
          <i className="bi bi-exclamation-triangle-fill me-2" />
          <strong>Error:</strong> {state.error}
          <button
            type="button"
            className="btn-close"
            onClick={() => dispatch({ type: ActionTypes.CLEAR_ERROR })}
            aria-label="Close"
          />
        </div>
      )}

      {/* Tab navigation */}
      <ul className="nav nav-tabs" style={{ flex: '0 0 auto' }}>
        {TABS.map((tab) => (
          <li key={tab.id} className="nav-item">
            <button
              className={`nav-link${activeTab === tab.id ? ' active' : ''}`}
              onClick={() => handleTabChange(tab.id)}
              style={{ fontSize: '0.88rem', padding: '6px 16px' }}
            >
              {tab.label}
            </button>
          </li>
        ))}
      </ul>

      {/* Tab content — all tabs kept mounted once visited, hidden via display:none */}
      <div style={{ flex: '1 1 0', minHeight: 0, position: 'relative' }}>

        {visitedTabs.has('configurations') && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: activeTab === 'configurations' ? 'flex' : 'none',
              flexDirection: 'column',
            }}
          >
            <ConfigurationsSummaryTab isActive={activeTab === 'configurations'} />
          </div>
        )}

        {visitedTabs.has('locations') && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: activeTab === 'locations' ? 'flex' : 'none',
              flexDirection: 'column',
            }}
          >
            <LocationsSummaryTab isActive={activeTab === 'locations'} />
          </div>
        )}

        {visitedTabs.has('completeness') && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: activeTab === 'completeness' ? 'flex' : 'none',
              flexDirection: 'column',
            }}
          >
            <CompletenessTab isActive={activeTab === 'completeness'} />
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
