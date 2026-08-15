import { Container, Alert } from 'react-bootstrap';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Home, DashboardsHome } from '@/components/common';
import { DataDashboard } from '@/components/dashboards/data_management';
import { NwmdDashboard } from '@/components/dashboards/nwmd/index';
import { DataDashboardProvider } from '@/context/DataDashboardContext';
import { NwmdDashboardProvider } from '@/context/NwmdDashboardContext';
import { useAuth } from '@/features/auth';
import { ForecastDashboard, ForecastDashboardProvider } from '@/features/forecast';
import { RetrospectiveDashboardProvider, RetrospectiveDashboard } from '@/features/retrospective';
import AdminHome from '@/pages/admin/AdminHome';
import AdminLayout from '@/pages/admin/AdminLayout';
import ApiKeysAdmin from '@/pages/admin/ApiKeysAdmin';
import KeycloakAdmin from '@/pages/admin/KeycloakAdmin';
import Navbar from '@/shared/components/Navbar';

import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

const RequireAuth = ({ children }: React.PropsWithChildren) => {
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

const AdminRoute = ({ children }: React.PropsWithChildren) => {
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
                  <RetrospectiveDashboard />
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
