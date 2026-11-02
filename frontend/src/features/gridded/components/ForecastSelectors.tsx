import { Button, Col, Form, InputGroup } from 'react-bootstrap';

import { ActionTypes, useDashboard } from '../DashboardContext';
import { useGriddedSelection } from '../hooks/useGriddedSelection';

const LEAD_TIME = 'lead_time';
const LABELS: Record<string, string> = {
  lead_time: 'Lead Time (hours)',
  member: 'Ensemble Member',
};

// Controls for each forecast axis after the cycle: a pager for lead time, a select otherwise
// (e.g. member), and the valid time shown. Renders nothing for analysis datasets.
const ForecastSelectors = () => {
  const { state, dispatch } = useDashboard();
  const { fixedDims, values, selected, validTime } = useGriddedSelection();
  if (fixedDims.length === 0) return null;

  const select = (dim: string, value: string) =>
    dispatch({
      type: ActionTypes.UPDATE_MAP_FILTERS,
      payload: { fixedSelections: { ...state.mapFilters.fixedSelections, [dim]: value } },
    });

  const leadPager = (dim: string) => {
    const options = values[dim];
    const index = options.indexOf(selected[dim]);
    return (
      <>
        <InputGroup size="sm">
          <Button
            variant="outline-secondary"
            onClick={() => select(dim, options[index - 1])}
            disabled={index <= 0}
            title="Previous lead time"
          >
            &#9664;
          </Button>
          <Form.Control
            readOnly
            value={selected[dim] ?? ''}
            className="text-center"
            style={{ fontSize: '0.8rem' }}
          />
          <Button
            variant="outline-secondary"
            onClick={() => select(dim, options[index + 1])}
            disabled={index < 0 || index >= options.length - 1}
            title="Next lead time"
          >
            &#9654;
          </Button>
        </InputGroup>
        {options.length > 0 && (
          <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: '2px' }}>
            {index + 1} / {options.length}
          </div>
        )}
      </>
    );
  };

  return (
    <>
      {fixedDims.map((dim) => (
        <Col md={12} key={dim}>
          <Form.Group>
            <Form.Label className="small fw-bold d-block">{LABELS[dim] ?? dim}</Form.Label>
            {dim === LEAD_TIME ? (
              leadPager(dim)
            ) : (
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
            )}
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
