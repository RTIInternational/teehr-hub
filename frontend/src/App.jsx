import { Container, Alert } from 'react-bootstrap';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import AdminHome from './components/admin/AdminHome.jsx';
import AdminLayout from './components/admin/AdminLayout.jsx';
import ApiKeysAdmin from './components/admin/ApiKeysAdmin.jsx';
import KeycloakAdmin from './components/admin/KeycloakAdmin.jsx';
import { Home, DashboardsHome, Navbar } from './components/common';
import { DataDashboard } from './components/dashboards/data_management';
import { ForecastDashboard } from './components/dashboards/forecast';
import { Dashboard } from './components/dashboards/retrospective';
import { NwmdDashboard } from './components/dashboards/nwmd/index.js';
import { DataDashboardProvider } from './context/DataDashboardContext.jsx';
import { ForecastDashboardProvider } from './context/ForecastDashboardContext.jsx';
import { NwmdDashboardProvider } from './context/NwmdDashboardContext.jsx';
import { RetrospectiveDashboardProvider } from './context/RetrospectiveDashboardContext.jsx';
import { useAuth } from './hooks/useAuth.js';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

const RequireAuth = ({ children }) => {
  const { ready, authenticated, login, signup } = useAuth();
  const location = useLocation();

  if (!ready) {
    return null;
  }

  if (!authenticated) {
    const redirectUri = `${window.location.origin}${location.pathname}${location.search}`;

    return (
      <Container className="mt-5 text-center">
        <Alert variant="info">
          <Alert.Heading>Login Required</Alert.Heading>
          <p>Please login to access the TEEHR dashboards.</p>
          <div className="d-flex justify-content-center gap-2 flex-wrap">
            <button
              type="button"
              className="btn btn-success"
              onClick={() => login({ redirectUri })}
            >
              Login
            </button>
            <button
              type="button"
              className="btn btn-outline-primary"
              onClick={() => signup(redirectUri)}
            >
              Sign Up
            </button>
          </div>
        </Alert>
      </Container>
    );
  }

  return children;
};

const AdminRoute = ({ children }) => {
  const { ready, authenticated, roles } = useAuth();

  if (!ready) {
    return null;
  }

  if (!authenticated) {
    return <Navigate to="/hub" replace />;
  }

  if (!roles.includes('admin')) {
    return (
      <Container className="mt-5 text-center">
        <Alert variant="danger">
          <Alert.Heading>Access Denied</Alert.Heading>
          <p>Admin role required.</p>
        </Alert>
      </Container>
    );
  }

  return children;
};

const AppRoutes = () => {
  return (
    <div className="App">
      <Navbar />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/hub" element={<DashboardsHome />} />
          {/* Redirect old dashboard route to retrospective */}
          <Route path="/dashboard" element={<Navigate to="/retrospective" replace />} />
          <Route
            path="/retrospective"
            element={
              <RequireAuth>
                <RetrospectiveDashboardProvider>
                  <Dashboard />
                </RetrospectiveDashboardProvider>
              </RequireAuth>
            }
          />
          {/* Future routes */}
          <Route
            path="/forecast"
            element={
              <RequireAuth>
                <ForecastDashboardProvider>
                  <ForecastDashboard />
                </ForecastDashboardProvider>
              </RequireAuth>
            }
          />
          <Route
            path="/data"
            element={
              <RequireAuth>
                <DataDashboardProvider>
                  <DataDashboard />
                </DataDashboardProvider>
              </RequireAuth>
            }
          />
          <Route
            path="/nwmd"
            element={
              <RequireAuth>
                <NwmdDashboardProvider>
                  <NwmdDashboard />
                </NwmdDashboardProvider>
              </RequireAuth>
            }
          />
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <AdminLayout />
              </AdminRoute>
            }
          >
            <Route index element={<AdminHome />} />
            <Route path="api-keys" element={<ApiKeysAdmin />} />
            <Route path="keycloak" element={<KeycloakAdmin />} />
          </Route>
        </Routes>
      </main>
    </div>
  );
};

function App() {
  return (
    <Router>
      <AppRoutes />
    </Router>
  );
}

export default App;
