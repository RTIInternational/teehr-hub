import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Form from 'react-bootstrap/Form';
import Row from 'react-bootstrap/Row';

import { useDistinctValues } from '@/shared/queries/distinctValues';

const TABLE = 'locations_metrics';
export const NULL_VALUE = 'null'; // sent to the API to match pre-computed "null" rows

/**
 * Convert a raw quantile key (e.g. "q_10th") to a readable label ("10th Percentile").
 * Falls back to the raw value for unrecognised strings.
 */
export const formatQuantileLabel = (value: string): string => {
  const match = value.match(/^q_(\d+)th$/i);
  if (match) return `${match[1]}th Percentile`;
  return value;
};

type SeasonQuantileFiltersProps = {
  season: string;
  setSeason: (value: string) => void;
  threshold: string;
  setThreshold: (value: string) => void;
};

export const SeasonQuantileFilters = ({
  season,
  setSeason,
  threshold,
  setThreshold,
}: SeasonQuantileFiltersProps) => {
  const seasons = useDistinctValues(TABLE, 'season');
  const thresholds = useDistinctValues(TABLE, 'threshold');

  return (
    <Card className="mb-3 border-0 shadow-sm">
      <Card.Body className="py-2 px-3">
        <Row className="g-3 align-items-end">
          <Col xs="auto">
            <Form.Group controlId="firo-season">
              <Form.Label className="small fw-semibold mb-1">Season</Form.Label>
              <Form.Select
                size="sm"
                value={season}
                onChange={(e) => setSeason(e.target.value)}
                style={{ minWidth: '160px' }}
                disabled={seasons.isLoading}
              >
                <option value={NULL_VALUE}>All Seasons</option>
                {seasons.data
                  ?.filter((s) => s !== null && s !== 'null' && s !== 'None')
                  .map((s) => (
                    <option key={s} value={s}>
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </option>
                  ))}
              </Form.Select>
            </Form.Group>
          </Col>

          <Col xs="auto">
            <Form.Group controlId="firo-quantile">
              <Form.Label className="small fw-semibold mb-1">Observed Flow Quantile</Form.Label>
              <Form.Select
                size="sm"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                style={{ minWidth: '220px' }}
                disabled={thresholds.isLoading}
              >
                <option value={NULL_VALUE}>All Quantiles</option>
                {thresholds.data
                  ?.filter((t) => t !== null && t !== 'null' && t !== 'None')
                  .map((t) => (
                    <option key={t} value={t}>
                      {formatQuantileLabel(t)}
                    </option>
                  ))}
              </Form.Select>
            </Form.Group>
          </Col>
        </Row>
      </Card.Body>
    </Card>
  );
};
