import Alert from 'react-bootstrap/Alert';
import { Outlet } from 'react-router-dom';

import { Sidebar } from './components/Sidebar';
import { useFiroDashboardStore, useFiroActions } from './store';

export const Dashboard = () => {
  const error = useFiroDashboardStore((s) => s.error);
  const { clearError } = useFiroActions();

  return (
    <div className="d-flex flex-column" style={{ height: 'calc(100dvh - 56px)' }}>
      {error && (
        <Alert
          variant="danger"
          dismissible
          onClose={clearError}
          className="m-0 rounded-0 border-0 border-bottom"
        >
          <i className="bi bi-exclamation-triangle-fill me-2" />
          <strong>Error:</strong> {error}
        </Alert>
      )}

      <div className="d-flex flex-row flex-grow-1" style={{ minHeight: 0 }}>
        <Sidebar />

        <main className="flex-grow-1 overflow-hidden" style={{ minHeight: 0, minWidth: 0 }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};
