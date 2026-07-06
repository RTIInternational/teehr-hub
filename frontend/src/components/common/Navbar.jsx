import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth.js';

const JUPYTERHUB_URL =
  import.meta.env.VITE_JUPYTERHUB_URL || 'https://hub.teehr.local.app.garden/hub/spawn';

const Navbar = () => {
  const location = useLocation();
  const isHome = location.pathname === '/';
  const { ready, authenticated, username, roles, login, signup, logout } = useAuth();
  const isAdmin = roles.includes('admin');
  const canViewHubDeployment = authenticated && roles.includes('jupyter-user');
  const [isDashboardsOpen, setIsDashboardsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [profileMenuStyle, setProfileMenuStyle] = useState({});
  const dashboardsDropdownRef = useRef(null);
  const profileDropdownRef = useRef(null);
  const profileButtonRef = useRef(null);
  const profileMenuRef = useRef(null);

  useEffect(() => {
    const handleDocumentClick = (event) => {
      if (dashboardsDropdownRef.current && !dashboardsDropdownRef.current.contains(event.target)) {
        setIsDashboardsOpen(false);
      }

      if (profileDropdownRef.current && !profileDropdownRef.current.contains(event.target)) {
        setIsProfileOpen(false);
      }
    };

    document.addEventListener('mousedown', handleDocumentClick);
    return () => {
      document.removeEventListener('mousedown', handleDocumentClick);
    };
  }, []);

  useEffect(() => {
    setIsDashboardsOpen(false);
    setIsProfileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!isProfileOpen) return;

    const updateMenuPosition = () => {
      if (!profileButtonRef.current || !profileMenuRef.current) return;

      const margin = 8;
      const buttonRect = profileButtonRef.current.getBoundingClientRect();
      const menuEl = profileMenuRef.current;
      const menuWidth = Math.min(352, window.innerWidth - margin * 2);

      // Measure height after width is known so we can keep the menu in the viewport.
      menuEl.style.width = `${menuWidth}px`;
      const menuHeight = menuEl.offsetHeight;

      let left = buttonRect.right - menuWidth;
      left = Math.max(margin, Math.min(left, window.innerWidth - menuWidth - margin));

      let top = buttonRect.bottom + 4;
      if (top + menuHeight > window.innerHeight - margin) {
        top = Math.max(margin, buttonRect.top - menuHeight - 4);
      }

      setProfileMenuStyle({
        position: 'fixed',
        left: `${left}px`,
        top: `${top}px`,
        width: `${menuWidth}px`,
        maxWidth: `${menuWidth}px`,
        maxHeight: `calc(100vh - ${margin * 2}px)`,
        overflowY: 'auto',
      });
    };

    updateMenuPosition();
    window.addEventListener('resize', updateMenuPosition);
    window.addEventListener('scroll', updateMenuPosition, true);

    return () => {
      window.removeEventListener('resize', updateMenuPosition);
      window.removeEventListener('scroll', updateMenuPosition, true);
    };
  }, [isProfileOpen, username, isAdmin]);

  const getBreadcrumbs = () => {
    const pathMap = {
      '/retrospective': 'Retrospective Simulations',
      '/forecast': 'Forecast Analysis',
      '/data': 'Data Availability',
      '/nwmd': 'National Water Model Diagnostics',
      '/admin': 'Admin Page',
      '/admin/api-keys': 'API Keys',
      '/admin/keycloak': 'Keycloak Admin',
    };

    if (isHome) return null;

    const isHubMainPage = location.pathname === '/hub' || location.pathname === '/hub/';

    return (
      <nav aria-label="breadcrumb">
        <ol className="breadcrumb mb-0 bg-transparent">
          <li className="breadcrumb-item">
            <Link to="/" className="text-light text-decoration-none">
              Home
            </Link>
          </li>
          <li className="breadcrumb-item">
            <Link to="/hub" className="text-light text-decoration-none">
              Dashboard Hub
            </Link>
          </li>
          {!isHubMainPage && (
            <li className="breadcrumb-item active text-white" aria-current="page">
              {pathMap[location.pathname] || 'Dashboard'}
            </li>
          )}
        </ol>
      </nav>
    );
  };

  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-primary">
      <div className="container-fluid px-4 d-flex align-items-center">
        <div className="navbar-brand me-3 d-flex align-items-center gap-2">
          <Link to="/" className="d-inline-flex align-items-center" aria-label="TEEHR-Cloud Home">
            <img
              src="/teehr.png"
              alt="TEEHR Dashboard"
              height="32"
              className="d-inline-block align-text-top navbar-teehr-logo"
            />
          </Link>
          <Link to="https://ciroh.ua.edu/" className="d-inline-flex align-items-center" aria-label="CIROH Home">
            <img
              src="https://raw.githubusercontent.com/RTIInternational/teehr/main/docs/images/readme/CIROHLogo_200x200.png"
              alt="CIROH logo"
              height="32"
              className="navbar-ciroh-logo"
            />
          </Link>
          <div className="dropdown" ref={dashboardsDropdownRef}>
            <button
              className="btn btn-outline-light btn-sm dropdown-toggle d-inline-flex align-items-center navbar-dashboard-toggle"
              type="button"
              onClick={() => {
                setIsDashboardsOpen((prev) => !prev);
                setIsProfileOpen(false);
              }}
              aria-expanded={isDashboardsOpen}
            >
              Dashboards
            </button>
            <ul className={`dropdown-menu${isDashboardsOpen ? ' show' : ''}`}>
              <li>
                <Link className="dropdown-item" to="/hub" onClick={() => setIsDashboardsOpen(false)}>
                  Dashboard Hub
                </Link>
              </li>
              <li>
                <Link className="dropdown-item ps-4" to="/data" onClick={() => setIsDashboardsOpen(false)}>
                  Data Availability
                </Link>
              </li>
              <li>
                <Link className="dropdown-item ps-4" to="/retrospective" onClick={() => setIsDashboardsOpen(false)}>
                  Retrospective Simulations
                </Link>
              </li>
              <li>
                <Link className="dropdown-item ps-4" to="/forecast" onClick={() => setIsDashboardsOpen(false)}>
                  Forecast Analysis
                </Link>
              </li>
            </ul>
          </div>
          {canViewHubDeployment && (
            <a
              className="btn btn-outline-light btn-sm d-inline-flex align-items-center"
              href={JUPYTERHUB_URL}
              target="_blank"
              rel="noreferrer"
            >
              JupyterHub
            </a>
          )}
        </div>

        {/* Breadcrumb Navigation */}
        <div className="flex-grow-1 d-flex align-items-center">
          {getBreadcrumbs()}
        </div>

        {/* User Profile Section */}
        <div className="d-flex align-items-center gap-2">
          <a className="btn btn-outline-light btn-sm" href="mailto:ciroh.teehr@gmail.com">
            Contact Us
          </a>

          {!ready && (
            <button className="btn btn-outline-light btn-sm" disabled>
              Auth Loading...
            </button>
          )}

          {ready && authenticated && (
            <div className="dropdown" ref={profileDropdownRef}>
              <button
                className="btn btn-outline-light btn-sm dropdown-toggle"
                type="button"
                ref={profileButtonRef}
                onClick={() => setIsProfileOpen((prev) => !prev)}
                aria-expanded={isProfileOpen}
              >
                Profile
              </button>
              <ul
                ref={profileMenuRef}
                className={`dropdown-menu${isProfileOpen ? ' show' : ''}`}
                style={profileMenuStyle}
              >
                <li>
                  <span className="dropdown-item-text text-wrap" style={{ overflowWrap: 'anywhere' }}>
                    Signed in as {username || 'user'}
                  </span>
                </li>
                {isAdmin && (
                  <li>
                    <Link
                      className="dropdown-item"
                      to="/admin"
                      onClick={() => setIsProfileOpen(false)}
                    >
                      Admin Page
                    </Link>
                  </li>
                )}
                <li><hr className="dropdown-divider" /></li>
                <li>
                  <button
                    className="dropdown-item"
                    type="button"
                    onClick={() => {
                      setIsProfileOpen(false);
                      logout();
                    }}
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          )}

          {ready && !authenticated && (
            <div className="d-flex align-items-center gap-2">
              <button className="btn btn-outline-light btn-sm" onClick={() => signup(window.location.href)}>
                Sign Up
              </button>
              <button className="btn btn-success btn-sm" onClick={() => login({ redirectUri: window.location.href })}>
                Login
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;