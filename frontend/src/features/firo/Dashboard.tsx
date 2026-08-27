import Alert from 'react-bootstrap/Alert';
import { Outlet } from 'react-router-dom';

import { Sidebar } from './components/Sidebar';
import { useFiroDashboardStore, useFiroActions } from './store';

import './firo-theme.css';

export const Dashboard = () => {
  const error = useFiroDashboardStore((s) => s.error);
  const { clearError } = useFiroActions();

  return (
    <div className="firo-theme d-flex flex-column" style={{ height: 'calc(100dvh - 56px)' }}>
      {error && (
        <Alert
          variant="danger"
          dismissible
          onClose={clearError}
          className="m-0 rounded-0 border-0 border-bottom firo-alert"
        >
          <i className="bi bi-exclamation-triangle-fill me-2" />
          <strong>Error:</strong> {error}
        </Alert>
      )}

      <div className="firo-shell d-flex flex-grow-1">
        <Sidebar />

        <main className="firo-main flex-grow-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
