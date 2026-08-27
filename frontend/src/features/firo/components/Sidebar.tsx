import { NavLink, useLocation, useNavigate } from 'react-router-dom';

import { useFiroDashboardStore } from '../store';

import './Sidebar.css';

const ANALYSIS_PAGES = [
  { key: 'deterministic', label: 'Deterministic', path: '/firo/detailed-analysis/deterministic' },
  {
    key: 'full-distribution',
    label: 'Full Distribution',
    path: '/firo/detailed-analysis/full-distribution',
  },
  {
    key: 'event-thresholds',
    label: 'Event Thresholds',
    path: '/firo/detailed-analysis/event-thresholds',
  },
];

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
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const analysisDisabled = selectedLocation === null;

  return (
    <div className="firo-sidebar d-flex flex-column">
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
            label="Top Events Performance"
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
