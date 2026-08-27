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
    className={
      active ? 'sidebar-btn--active' : disabled ? 'sidebar-btn--disabled' : 'sidebar-btn--idle'
    }
    style={{
      display: 'flex',
      alignItems: 'center',
      width: '100%',
      padding: '0.45rem 0.75rem',
      borderRadius: '6px',
      textAlign: 'left',
      fontSize: '0.875rem',
      textDecoration: 'none',
      cursor: disabled ? 'not-allowed' : 'pointer',
      transition: 'background 0.15s, color 0.15s, border-color 0.15s',
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
    <div
      className="d-flex flex-column border-end"
      style={{
        width: '235px',
        minWidth: '235px',
        height: '100%',
        overflowY: 'auto',
        background: '#f8f9fa',
      }}
    >
      {/* Header */}
      <div className="px-3 pt-3 pb-2 border-bottom">
        <span
          className="text-uppercase text-secondary fw-semibold"
          style={{ fontSize: '0.7rem', letterSpacing: '0.08em' }}
        >
          Workflow
        </span>
      </div>

      <div className="px-2 py-2 d-flex flex-column gap-1">
        {/* 1 — Location Selection */}
        <NavButton
          label="Location Selection"
          active={pathname.startsWith('/firo/location-selection')}
          onClick={() => navigate('/firo/location-selection')}
        />

        {/* Sub-heading — Detailed Location Analysis */}
        <div
          className="d-flex align-items-center px-1 mt-2"
          style={{
            borderLeft: `2px solid ${analysisDisabled ? '#dee2e6' : '#0d6efd'}`,
            paddingLeft: '0.4rem',
          }}
        >
          <span
            className="fw-semibold"
            style={{
              fontSize: '0.75rem',
              color: analysisDisabled ? '#adb5bd' : '#495057',
              letterSpacing: '0.01em',
            }}
          >
            Detailed Location Analysis
          </span>
        </div>

        {/* Analysis sub-pages — indented by wrapping in a left-padded container */}
        <div style={{ paddingLeft: '0.75rem' }}>
          <div className="d-flex flex-column gap-1">
            {ANALYSIS_PAGES.map((page) =>
              analysisDisabled ? (
                <NavButton key={page.key} label={page.label} disabled />
              ) : (
                <NavLink
                  key={page.key}
                  to={page.path}
                  className={({ isActive }) =>
                    isActive ? 'sidebar-btn--active' : 'sidebar-btn--idle'
                  }
                  style={({ isActive }) => ({
                    display: 'flex',
                    alignItems: 'center',
                    width: '100%',
                    padding: '0.45rem 0.75rem',
                    borderRadius: '6px',
                    fontSize: '0.875rem',
                    textDecoration: 'none',
                    transition: 'background 0.15s, color 0.15s',
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

      {/* Selected location summary */}
      {selectedLocation && (
        <div className="mt-auto px-3 py-3 border-top">
          <p
            className="text-muted mb-1"
            style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}
          >
            Selected Location
          </p>
          <p className="small fw-semibold mb-0 text-truncate" title={selectedLocation.name}>
            {selectedLocation.name}
          </p>
          <p className="text-muted mb-0" style={{ fontSize: '0.7rem' }}>
            {selectedLocation.primary_location_id}
          </p>
        </div>
      )}
    </div>
  );
};
