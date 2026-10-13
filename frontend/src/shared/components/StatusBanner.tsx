import { useState } from 'react';
import { Alert } from 'react-bootstrap';

import { usePlatformStatus } from '@/shared/queries/platformStatus';

const DISMISSED_KEY = 'teehr-status-dismissed';

const readDismissed = () => {
  try {
    return sessionStorage.getItem(DISMISSED_KEY);
  } catch {
    return null;
  }
};

// Overlays the page below the navbar rather than taking layout space, since
// the dashboards size themselves to the viewport minus the navbar.
const StatusBanner = () => {
  const { data } = usePlatformStatus();
  const [dismissed, setDismissed] = useState(readDismissed);
  const message = data?.message;

  if (!message || message === dismissed) {
    return null;
  }

  const dismiss = () => {
    setDismissed(message);
    try {
      sessionStorage.setItem(DISMISSED_KEY, message);
    } catch {
      // Storage unavailable; dismissal lasts until reload.
    }
  };

  return (
    <Alert
      variant="warning"
      dismissible
      onClose={dismiss}
      className="shadow mb-0"
      style={{
        position: 'fixed',
        top: '64px',
        left: '50%',
        transform: 'translateX(-50%)',
        width: 'calc(100% - 32px)',
        maxWidth: '720px',
        zIndex: 1350,
      }}
    >
      {message}
    </Alert>
  );
};

export default StatusBanner;
