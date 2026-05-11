import { useEffect, useState } from 'react';
import { Spinner, Alert } from 'react-bootstrap';
import { apiService } from '../../../services/api';

const formatDatetime = (val) => {
  if (!val) return '—';
  return String(val).replace('T', ' ').replace(/\.\d+Z?$/, '');
};

const AttributesPanel = () => {
  const [attributes, setAttributes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [collapsed, setCollapsed] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    apiService.getAttributes()
      .then((data) => setAttributes(data.items || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="d-flex flex-column h-100" style={{ overflow: 'hidden' }}>
      <div
        className="px-3 pt-3 pb-2 border-bottom d-flex align-items-center justify-content-between"
        style={{ flexShrink: 0, cursor: 'pointer', userSelect: 'none' }}
        onClick={() => setCollapsed((c) => !c)}
      >
        <h6 className="mb-0 fw-semibold">Attributes</h6>
        <i className={`bi bi-chevron-${collapsed ? 'down' : 'up'}`} style={{ fontSize: '0.8rem', color: '#6c757d' }}></i>
      </div>

      {!collapsed && (
        <div style={{ overflowY: 'auto', flex: 1 }}>
        {loading && (
          <div className="d-flex align-items-center justify-content-center h-100">
            <Spinner animation="border" variant="primary" role="status">
              <span className="visually-hidden">Loading attributes...</span>
            </Spinner>
          </div>
        )}

        {!loading && error && (
          <Alert variant="danger" className="m-2">
            <i className="bi bi-exclamation-triangle-fill me-2"></i>
            {error}
          </Alert>
        )}

        {!loading && !error && attributes.length === 0 && (
          <div className="d-flex align-items-center justify-content-center h-100 text-muted">
            <span>No attributes available.</span>
          </div>
        )}

        {!loading && !error && attributes.length > 0 && (
          <ul className="list-group list-group-flush">
            {attributes.map((attr, idx) => (
              <li key={attr.name ?? idx} className="list-group-item px-3 py-2">
                <div className="fw-semibold" style={{ fontSize: '0.85rem' }}>{attr.description ?? '—'}</div>
                {attr.name && (
                  <div className="text-muted" style={{ fontSize: '0.78rem' }}>{attr.name}</div>
                )}
                <div className="d-flex gap-3 mt-1" style={{ fontSize: '0.75rem', color: '#6c757d' }}>
                  {attr.type && (
                    <span><span className="fw-semibold">Type:</span> {attr.type}</span>
                  )}
                  {attr.updated_at && (
                    <span><span className="fw-semibold">Updated:</span> {formatDatetime(attr.updated_at)}</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      )}
    </div>
  );
};

export default AttributesPanel;
