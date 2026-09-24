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
      '/gridded': 'Gridded Data',
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
          <Link
            to="https://www.rti.org/focus-area/water-forecasting-operations"
            className="d-inline-flex align-items-center"
            aria-label="RTI International Home"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="32"
              viewBox="0 0 199 80"
              // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
              role="img"
              aria-label="RTI International Logo"
            >
              <g fill="none" fill-rule="nonzero">
                <path
                  fill="#FFFFFF"
                  d="M59.89 60.667H32.393c16.803-11.21 31.175-30.135 11.794-41.5 17.937 18.86-12.26 35.88-33.174 41.5H-.001v-49.46c7.37-1.158 15.975-1.361 26.266-.111C18.474 8.814 9.368 7.217 0 6.361V.777h45.875c-16.726 11.22-30.926 30.056-11.612 41.378-15.731-16.541 6.04-31.664 25.627-38.922v57.434z"
                ></path>
                <path
                  fill="#ffffff"
                  d="M180.166 37.826c0 7.542 0 13.683-.391 16.95-.234 2.25-.7 3.575-2.25 3.889-.7.153-1.634.308-2.806.308-.928 0-1.242.234-1.242.625 0 .542.548.775 1.556.775 3.108 0 8.014-.233 9.806-.233 2.094 0 6.997.233 12.13.233.85 0 1.475-.233 1.475-.775 0-.391-.391-.625-1.247-.625-1.167 0-2.875-.155-3.961-.308-2.34-.314-2.88-1.714-3.114-3.814-.308-3.342-.308-9.483-.308-17.025V24.137c0-11.82 0-13.997.15-16.486.158-2.722.777-4.044 2.88-4.43.934-.156 1.553-.24 2.334-.24.777 0 1.244-.152 1.244-.774 0-.467-.625-.623-1.633-.623-2.953 0-7.542.234-9.49.234-2.252 0-7.158-.234-10.108-.234-1.247 0-1.866.156-1.866.623 0 .622.466.775 1.247.775.933 0 1.944.083 2.8.314 1.703.386 2.486 1.71 2.642 4.355.152 2.489.152 4.667.152 16.486v13.69-.001zM.263 79.308v-.142c.428 0 .683-.352.683-1.1V69.89c0-.77-.28-1.1-.683-1.1v-.136H3.55v.136c-.53 0-.73.391-.73 1.144v8.094c0 .973.286 1.14.73 1.14v.141H.263v-.001zm20.483-9.445v9.95l-7.705-9.44V78.1c0 .655.297 1.07.753 1.07v.138H11.41v-.139c.5-.114.728-.214.728-1.041v-8.15c0-.867-.314-1.19-.711-1.19v-.135h2.611l5.794 7.147v-5.88c0-.842-.3-1.131-.755-1.131v-.136h2.339v.136c-.525.12-.67.33-.67 1.075m17.072.281l-.142-.011c-.056-.456-.156-.614-2.114-.614h-1.083v8.508c0 .9.341 1.111.741 1.139v.142h-3.34v-.142c.544 0 .727-.353.727-1.1V69.52h-1.352c-1.542 0-1.887.125-1.9.57l-.145.044-.341-1.48h9.294l-.344 1.49-.001.001zm14.588 9.163h-6.653v-.142c.445 0 .673-.341.673-1.1V69.82c0-.797-.356-1.03-.759-1.03v-.136h6.609l-.212 1.463-.158-.013c.014-.5-.255-.598-1.828-.598h-1.77v3.97h1.67c1.973 0 1.842-.19 1.986-.592h.145v2.089h-.145c-.113-.486-.402-.639-2-.639H48.31V77.6c0 .77.228.855.986.855h1.625c.917 0 1.797-.314 2.07-.855l.144.07-.728 1.638h-.001zm17.356 0v-.153c-.228-.03-.572-.216-.997-.844l-2.814-4.142c.87-.253 2.055-1.236 2.055-2.653 0-3.2-3.725-2.864-4.266-2.864h-3.1v.137c.514 0 .741.444.741 1.1v8.177c0 .873-.283 1.048-.725 1.1v.142h3.312v-.142c-.442-.114-.731-.155-.731-1.138v-3.412c.33 0 .617.014.928-.027l3.055 4.72h2.542v-.001zm-3.653-7.72c0 1.295-.814 2.256-2.597 2.256h-.275v-4.436h.672c1.3 0 2.2.867 2.2 2.18zm20.181-1.725v9.95l-7.705-9.44V78.1c0 .655.3 1.07.755 1.07v.138h-2.38v-.139c.494-.114.722-.214.722-1.041v-8.15c0-.867-.314-1.19-.708-1.19v-.135h2.61l5.792 7.147v-5.88c0-.842-.3-1.131-.755-1.131v-.136h2.342v.136c-.528.12-.673.33-.673 1.075m18.012 9.444v-.142c-.4 0-.614-.325-.77-.752l-3.71-9.761h-2.014v.136c.097 0 .6.102.355.758l-3.31 8.936c-.14.403-.445.683-.756.683v.142h2v-.142c-.328 0-.473-.352-.342-.71l.997-2.773h3.753l.986 2.73c.145.4.086.753-.4.753v.142h3.211zm-4.083-4.422h-3.18l1.569-4.356 1.61 4.356h.001zm18.245-4.741l-.147-.011c-.053-.456-.156-.614-2.109-.614h-1.086v8.508c0 .9.342 1.111.742 1.139v.142h-3.342v-.142c.545 0 .728-.353.728-1.1V69.52h-1.356c-1.541 0-1.883.125-1.894.57l-.147.044-.342-1.48h9.289l-.336 1.49v.001zm7.861 9.163v-.142c.428 0 .69-.352.69-1.1V69.89c0-.77-.287-1.1-.69-1.1v-.136h3.284v.136c-.528 0-.728.391-.728 1.144v8.094c0 .973.286 1.14.728 1.14v.141h-3.284v-.001zm22.483-5.295c0-2.983-2.214-5.578-5.54-5.578-3.982 0-5.707 2.767-5.707 5.54 0 2.782 1.866 5.55 5.594 5.55 3.78 0 5.653-2.695 5.653-5.512m-1.959-.097c0 3.867-2.355 4.77-3.636 4.77-2.67 0-3.683-2.531-3.683-4.64 0-3.341 1.611-4.71 3.694-4.71 2.442 0 3.625 2.269 3.625 4.58m19.277-4.053v9.95l-7.709-9.44V78.1c0 .655.297 1.07.753 1.07v.138h-2.38v-.139c.497-.114.724-.214.724-1.041v-8.15c0-.867-.313-1.19-.713-1.19v-.135h2.613l5.795 7.147v-5.88c0-.842-.297-1.131-.756-1.131v-.136h2.34v.136c-.531.12-.667.33-.667 1.075m18.006 9.444v-.142c-.403 0-.614-.325-.77-.752l-3.71-9.761h-2.014v.136c.103 0 .597.102.358.758l-3.314 8.936c-.141.403-.441.683-.755.683v.142h1.997v-.142c-.325 0-.472-.352-.342-.71l.997-2.773h3.756l.986 2.73c.142.4.089.753-.4.753v.142h3.211zm-4.08-4.422h-3.184l1.567-4.356 1.617 4.356zm18.056 4.422h-6.609v-.142c.414-.027.673-.341.673-1.1V69.89c0-.7-.286-1.1-.759-1.1v-.136h3.325v.136c-.244 0-.672.13-.672 1.075v7.92c0 .569.272.7.83.7h1.167c1.23 0 2.228-.218 2.614-.884l.142.07-.711 1.638v-.001zM71.61 37.517c.002 7.233.002 13.439-.392 16.736-.312 2.28-.709 4.01-2.281 4.325-.706.158-1.65.314-2.825.314-.944 0-1.258.233-1.258.625 0 .552.55.786 1.57.786 3.146 0 8.093-.234 9.588-.234 1.178 0 6.992.234 11.547.234 1.02 0 1.572-.234 1.57-.786 0-.392-.314-.625-.942-.625-.942 0-2.67-.156-3.847-.314-2.359-.314-2.83-2.045-3.067-4.325-.389-3.297-.389-9.503-.392-16.811V8.569c0-.005-.02-1.247-.02-1.627 0-1.667 0-1.925 1.279-2.142 1.536-.264 3.808-.27 5.297-.086 1.77.22 3.5 1.014 4.842 1.947 1.26.878 4.058 2.958 5.086 8.22 1.091 5.588-.059 11.558-3.103 14.916-1.364 1.509-2.783 2.647-4.511 3.52-2.678 1.358-4.336 1.66-5.175 1.997-.67.267-1.606.603-1.906.775-.516.3-.464.467.434.43 1.383-.06 4.833-.522 5.3-.597.42-.06.964.028 1.352.497 1.023 1.178 4.636 6.523 7.78 10.842 4.4 6.05 7.387 9.745 10.765 11.55 2.041 1.103 4.005 1.492 8.405 1.492h7.464c.945 0 1.492-.159 1.492-.786 0-.392-.314-.625-.942-.625-.625 0-1.336-.08-2.197-.24-1.178-.238-4.4-.785-8.8-5.34-4.639-4.873-10.058-11.862-17.053-20.662 7.823-5.47 10.373-11.783 10.373-17.6 0-5.264-3.145-9.27-5.342-10.761C97.456 1.38 92.193.909 87.243.909c-2.437 0-8.406.235-11.078.235-1.65 0-6.598-.236-10.761-.236-1.18 0-1.728.156-1.728.709 0 .547.47.705 1.33.705 1.103 0 2.44.078 3.07.236 2.589.55 3.22 1.806 3.372 4.478.161 2.514.161 4.714.161 16.656v13.825h.001zm83.464-35.69c3.056-.024 5.522-.158 7.775-.391 1.947-.153 4.047-.464 4.275.547.159.622 1.633 7.697 1.633 8.942 0 .858-.152 1.247-.7 1.247-.466 0-.694-.317-.858-.936-.15-.622-.542-1.556-1.317-2.722-1.166-1.711-2.93-2.095-7.541-2.253a2002.63001917 2002.63001917 0 00-12.578-.38l.3 31.944c0 7.152 0 13.3.389 16.641.239 2.175.7 3.884 3.033 4.198 1.092.152 2.8.31 3.967.31.864 0 1.242.234 1.242.623 0 .544-.623.778-1.48.778-5.129 0-10.026-.234-12.2-.234-1.787 0-6.693.234-9.8.234-1.01 0-1.556-.234-1.556-.778 0-.389.313-.622 1.247-.622 1.166 0 2.1-.159 2.8-.311 1.55-.314 2.016-2.023 2.25-4.275.391-3.264.391-9.412.391-16.564V5.939l-11.589.31c-4.508.156-6.375.548-7.541 2.256-.775 1.167-1.167 2.1-1.32 2.722-.16.62-.389.937-.855.937-.547 0-.7-.392-.7-1.25 0-1.242 1.475-8.32 1.633-8.94.228-1.013 2.328-.702 4.275-.544 2.25.23 5.209.386 7.78.386 0 0 23.984.034 27.045.011"
                ></path>
              </g>
            </svg>
          </Link>
          <Link
            className="btn btn-outline-light btn-sm d-inline-flex align-items-center"
            to={'/hub'}
          >
            Dashboards
          </Link>
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
