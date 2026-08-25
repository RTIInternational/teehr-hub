import { Dropdown } from 'react-bootstrap';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/features/auth';

const JUPYTERHUB_URL =
  import.meta.env.VITE_JUPYTERHUB_URL || 'https://hub.teehr.local.app.garden/hub/spawn';

const Navbar = () => {
  const location = useLocation();
  const isHome = location.pathname === '/';
  const { ready, authenticated, username, roles, login, signup, logout } = useAuth();
  const isAdmin = roles.includes('admin');
  const canViewHubDeployment = authenticated && roles.includes('jupyter-user');

  const getBreadcrumbs = () => {
    const pathMap: Record<string, string> = {
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
    <nav className="navbar navbar-expand-lg navbar-dark bg-primary" style={{ zIndex: 1300 }}>
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
          <Link
            to="https://ciroh.ua.edu/"
            className="d-inline-flex align-items-center"
            aria-label="CIROH Home"
          >
            <img
              src="https://raw.githubusercontent.com/RTIInternational/teehr/main/docs/images/readme/CIROHLogo_200x200.png"
              alt="CIROH logo"
              height="32"
              className="navbar-ciroh-logo"
            />
          </Link>
          <Dropdown key={location.pathname}>
            <Dropdown.Toggle
              variant="outline-light"
              size="sm"
              className="d-inline-flex align-items-center navbar-dashboard-toggle"
            >
              Dashboards
            </Dropdown.Toggle>
            <Dropdown.Menu>
              <Dropdown.Item as={Link} to="/hub">
                Dashboard Hub
              </Dropdown.Item>
              <Dropdown.Item as={Link} to="/data" className="ps-4">
                Data Availability
              </Dropdown.Item>
              <Dropdown.Item as={Link} to="/retrospective" className="ps-4">
                Retrospective Simulations
              </Dropdown.Item>
              <Dropdown.Item as={Link} to="/forecast" className="ps-4">
                Forecast Analysis
              </Dropdown.Item>
            </Dropdown.Menu>
          </Dropdown>
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
        <div className="flex-grow-1 d-flex align-items-center">{getBreadcrumbs()}</div>

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
            <Dropdown align="end" key={location.pathname}>
              <Dropdown.Toggle variant="outline-light" size="sm">
                Profile
              </Dropdown.Toggle>
              <Dropdown.Menu
                style={{ maxWidth: '352px', overflowY: 'auto', maxHeight: 'calc(100vh - 16px)' }}
              >
                <Dropdown.ItemText className="text-wrap" style={{ overflowWrap: 'anywhere' }}>
                  Signed in as {username || 'user'}
                </Dropdown.ItemText>
                {isAdmin && (
                  <Dropdown.Item as={Link} to="/admin">
                    Admin Page
                  </Dropdown.Item>
                )}
                <Dropdown.Divider />
                <Dropdown.Item as="button" onClick={logout}>
                  Logout
                </Dropdown.Item>
              </Dropdown.Menu>
            </Dropdown>
          )}

          {ready && !authenticated && (
            <div className="d-flex align-items-center gap-2">
              <button
                className="btn btn-outline-light btn-sm"
                onClick={() => signup(window.location.href)}
              >
                Sign Up
              </button>
              <button
                className="btn btn-success btn-sm"
                onClick={() => login({ redirectUri: window.location.href })}
              >
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
