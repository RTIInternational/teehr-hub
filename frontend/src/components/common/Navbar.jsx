import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth.js';

const Navbar = () => {
  const location = useLocation();
  const isHome = location.pathname === '/';
  const { ready, authenticated, username, roles, login, signup, logout } = useAuth();
  const isAdmin = roles.includes('admin');

  const getBreadcrumbs = () => {
    const pathMap = {
      '/retrospective': 'Retrospective Simulations',
      '/forecast': 'Forecast Analysis',
      '/data': 'Data Management'
    };

    if (isHome) return null;

    return (
      <nav aria-label="breadcrumb">
        <ol className="breadcrumb mb-0 bg-transparent">
          <li className="breadcrumb-item">
            <Link to="/" className="text-light text-decoration-none">
              Dashboard Hub
            </Link>
          </li>
          <li className="breadcrumb-item active text-white" aria-current="page">
            {pathMap[location.pathname] || 'Dashboard'}
          </li>
        </ol>
      </nav>
    );
  };

  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-primary">
      <div className="container-fluid px-4 d-flex align-items-center">
        <Link className="navbar-brand me-3" to="/">
          <img 
            src="/teehr.png" 
            alt="TEEHR Dashboard" 
            height="32" 
            className="d-inline-block align-text-top"
          />
        </Link>
        
        {/* Breadcrumb Navigation */}
        <div className="flex-grow-1 d-flex align-items-center">
          {getBreadcrumbs()}
        </div>
        
        {/* User Profile Section */}
        <div className="d-flex align-items-center">
          {ready && authenticated && isAdmin && (
            <Link className="btn btn-outline-light btn-sm me-2" to="/admin">
              Admin
            </Link>
          )}

          {!ready && (
            <button className="btn btn-outline-light btn-sm" disabled>
              Auth Loading...
            </button>
          )}

          {ready && authenticated && (
            <div className="d-flex align-items-center gap-2">
              <span className="text-white small d-none d-md-inline">
                Signed in as {username || 'user'}
              </span>
              <button className="btn btn-outline-light btn-sm" onClick={logout}>
                Logout
              </button>
            </div>
          )}

          {ready && !authenticated && (
            <div className="d-flex align-items-center gap-2">
              <button className="btn btn-success btn-sm" onClick={() => login({ redirectUri: window.location.href })}>
                Login
              </button>
              <button className="btn btn-outline-light btn-sm" onClick={() => signup(window.location.href)}>
                Sign Up
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;