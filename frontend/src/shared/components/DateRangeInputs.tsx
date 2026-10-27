import { Col, Form } from 'react-bootstrap';

type DateRangeInputsProps = {
  start: string | null;
  end: string | null;
  onStartChange: (value: string | null) => void;
  onEndChange: (value: string | null) => void;
  startLabel?: string;
  endLabel?: string;
};

const DateRangeInputs = ({
  start,
  end,
  onStartChange,
  onEndChange,
  startLabel = 'Start Date',
  endLabel = 'End Date',
}: DateRangeInputsProps) => (
  <>
    <Col md={6}>
      <Form.Group>
        <Form.Label className="small fw-bold">{startLabel}</Form.Label>
        <Form.Control
          type="datetime-local"
          size="sm"
          value={start || ''}
          onChange={(e) => onStartChange(e.target.value || null)}
        />
      </Form.Group>
    </Col>

    <Col md={6}>
      <Form.Group>
        <Form.Label className="small fw-bold">{endLabel}</Form.Label>
        <Form.Control
          type="datetime-local"
          size="sm"
          value={end || ''}
          onChange={(e) => onEndChange(e.target.value || null)}
        />
      </Form.Group>
    </Col>
  </>
);

export default DateRangeInputs;
