import { Col, Form } from 'react-bootstrap';

import { ActionTypes, useDashboard } from '../DashboardContext';
import { useGriddedSelection } from '../hooks/useGriddedSelection';

const LABELS: Record<string, string> = {
  lead_time: 'Lead Time (hours)',
  member: 'Ensemble Member',
};

// A select per forecast axis after the cycle (lead time, member), and the valid time shown.
// Renders nothing for analysis datasets.
const ForecastSelectors = () => {
  const { state, dispatch } = useDashboard();
  const { fixedDims, values, selected, validTime } = useGriddedSelection();
  if (fixedDims.length === 0) return null;

  const select = (dim: string, value: string) =>
    dispatch({
      type: ActionTypes.UPDATE_MAP_FILTERS,
      payload: { fixedSelections: { ...state.mapFilters.fixedSelections, [dim]: value } },
    });

  return (
    <>
      {fixedDims.map((dim) => (
        <Col md={12} key={dim}>
          <Form.Group>
            <Form.Label className="small fw-bold">{LABELS[dim] ?? dim}</Form.Label>
            <Form.Select
              size="sm"
              value={selected[dim] ?? ''}
              onChange={(e) => select(dim, e.target.value)}
              disabled={values[dim].length === 0}
            >
              {values[dim].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Form.Select>
          </Form.Group>
        </Col>
      ))}
      {validTime && (
        <Col md={12}>
          <div className="text-muted" style={{ fontSize: '0.75rem' }}>
            Valid {validTime.replace('T', ' ')} UTC
          </div>
        </Col>
      )}
    </>
  );
};

export default ForecastSelectors;
