import ButtonGroup from 'react-bootstrap/ButtonGroup';
import ToggleButton from 'react-bootstrap/ToggleButton';

export type LeadTimeGranularity = 'daily' | 'hourly';

type LeadTimeGranularityToggleProps = {
  value: LeadTimeGranularity;
  onChange: (value: LeadTimeGranularity) => void;
};

export const LeadTimeGranularityToggle = ({
  value,
  onChange,
}: LeadTimeGranularityToggleProps) => (
  <ButtonGroup size="sm">
    <ToggleButton
      id="granularity-daily"
      type="radio"
      variant="outline-primary"
      value="daily"
      checked={value === 'daily'}
      onChange={() => onChange('daily')}
    >
      Daily
    </ToggleButton>
    <ToggleButton
      id="granularity-hourly"
      type="radio"
      variant="outline-primary"
      value="hourly"
      checked={value === 'hourly'}
      onChange={() => onChange('hourly')}
    >
      Hourly
    </ToggleButton>
  </ButtonGroup>
);
