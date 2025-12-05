import { Link, useLocation } from 'react-router-dom';

const Navbar = () => {
  const location = useLocation();
  const isHome = location.pathname === '/';

  const getBreadcrumbs = () => {
    const pathMap = {
      '/dashboard': 'Retrospective Simulations',
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
          <div className="dropdown me-3">
            <button 
              className="btn btn-outline-light btn-sm dropdown-toggle d-flex align-items-center" 
              type="button" 
              id="userProfileDropdown" 
              data-bs-toggle="dropdown" 
              aria-expanded="false"
            >
              <i className="bi bi-person-circle me-1"></i>
              <span className="d-none d-sm-inline">Profile</span>
            </button>
            <ul className="dropdown-menu dropdown-menu-end" aria-labelledby="userProfileDropdown">
              <li><h6 className="dropdown-header">User Menu</h6></li>
              <li><a className="dropdown-item" href="#"><i className="bi bi-person me-2"></i>View Profile</a></li>
              <li><a className="dropdown-item" href="#"><i className="bi bi-gear me-2"></i>Settings</a></li>
              <li><hr className="dropdown-divider" /></li>
              <li><a className="dropdown-item" href="#"><i className="bi bi-box-arrow-right me-2"></i>Logout</a></li>
            </ul>
          </div>
          
          <button className="btn btn-success btn-sm">
            <i className="bi bi-box-arrow-in-right me-1"></i>
            <span className="d-none d-sm-inline">Login</span>
          </button>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;