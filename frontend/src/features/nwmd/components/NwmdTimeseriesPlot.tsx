import { useMemo, useState } from 'react';
import { Card, Spinner } from 'react-bootstrap';
import { Form } from 'react-bootstrap';

import PlotlyChart from '@/shared/components/PlotlyChart';
import { useDistinctValues } from '@/shared/queries/distinctValues';
import { usePrimaryTimeseries, useSecondaryTimeseries } from '@/shared/queries/timeseries';
import type { MapLocation } from '@/shared/types/locations';
import type { TimeseriesFilters } from '@/shared/types/timeseries';
import {
  filterWaterYearMonthOptions,
  getMonthDateRangeFromWaterYearMonth,
  getWaterYearMonthOptionsFromQuarters,
} from '@/shared/utils/dates';

import type { NwmdMapFilters } from '../types/maps';

const MONTH_ORDER = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9];

const monthRank = (monthNumber: number) => {
  const idx = MONTH_ORDER.indexOf(monthNumber);
  return idx < 0 ? Number.MAX_SAFE_INTEGER : idx;
};

const monthKey = (monthNumber: number) => String(monthNumber).padStart(2, '0');

type NwmdTimeseriesPlotProps = {
  table: string;
  mapFilters: NwmdMapFilters;
  selectedLocation: MapLocation | null;
  timeseriesFilters: TimeseriesFilters;
};

const NwmdTimeseriesPlot = ({
  table,
  mapFilters,
  selectedLocation,
  timeseriesFilters,
}: NwmdTimeseriesPlotProps) => {
  const quarters = useDistinctValues(table, 'quarter');

  const [waterYearPreference, setWaterYearPreference] = useState<string | null>(null);
  const [monthPreference, setMonthPreference] = useState<string | null>(null);

  const temporalOptions = useMemo(() => {
    const quarterValues = Array.isArray(quarters.data) ? quarters.data : [];
    const expanded = getWaterYearMonthOptionsFromQuarters(quarterValues);

    return filterWaterYearMonthOptions(expanded, {
      mapWaterYear: mapFilters.waterYear,
      mapQuarter: mapFilters.quarter,
      selectedWaterYear: null,
    });
  }, [quarters.data, mapFilters.waterYear, mapFilters.quarter]);

  const selectedWaterYear = useMemo(() => {
    const availableYears = temporalOptions.availableWaterYears;
    if (!availableYears.length) return null;

    if (waterYearPreference && availableYears.includes(waterYearPreference)) {
      return waterYearPreference;
    }

    return availableYears[0];
  }, [temporalOptions.availableWaterYears, waterYearPreference]);

  const availableMonths = useMemo(() => {
    const source = temporalOptions.constrained;
    if (!selectedWaterYear) return [];

    return source
      .filter((item) => item.waterYear === selectedWaterYear)
      .toSorted((a, b) => monthRank(a.monthNumber) - monthRank(b.monthNumber));
  }, [temporalOptions.constrained, selectedWaterYear]);

  const selectedMonth = useMemo(() => {
    if (!availableMonths.length) return null;

    if (
      monthPreference &&
      availableMonths.some((item) => monthKey(item.monthNumber) === monthPreference)
    ) {
      return monthPreference;
    }

    const mostRecentMonth = [...availableMonths].sort((a, b) => {
      if (a.calendarYear !== b.calendarYear) return b.calendarYear - a.calendarYear;
      return b.monthNumber - a.monthNumber;
    })[0];

    return monthKey(mostRecentMonth.monthNumber);
  }, [availableMonths, monthPreference]);

  const timeseriesFiltersForSelection = useMemo(() => {
    if (!selectedWaterYear || !selectedMonth) return timeseriesFilters;

    const monthNumber = Number.parseInt(selectedMonth, 10);
    if (!Number.isFinite(monthNumber)) return timeseriesFilters;

    const monthRange = getMonthDateRangeFromWaterYearMonth(selectedWaterYear, monthNumber);
    if (!monthRange) return timeseriesFilters;

    return {
      ...timeseriesFilters,
      primary: {
        ...timeseriesFilters.primary,
        start_date: monthRange.start_date,
        end_date: monthRange.end_date,
      },
      secondary: {
        ...timeseriesFilters.secondary,
        reference_start_date: monthRange.start_date,
        reference_end_date: monthRange.end_date,
      },
    };
  }, [timeseriesFilters, selectedWaterYear, selectedMonth]);

  const primary_location_id = selectedLocation?.primary_location_id;
  const primary = usePrimaryTimeseries({ primary_location_id, ...timeseriesFiltersForSelection });
  const secondary = useSecondaryTimeseries({
    primary_location_id,
    ...timeseriesFiltersForSelection,
  });

  const primaryData = primary.data ?? [];
  const secondaryData = secondary.data ?? [];

  const hasData = primaryData.length > 0 || secondaryData.length > 0;

  return (
    <Card className="shadow-lg h-100 d-flex flex-column" style={{ borderRadius: '8px' }}>
      <Card.Body className="p-0 d-flex flex-column flex-grow-1 overflow-hidden">
        <div className="px-2 pt-2 pb-1 border-bottom">
          <div className="d-flex gap-2">
            <Form.Group className="flex-grow-1" style={{ maxWidth: '150px' }}>
              <Form.Label className="small fw-bold mb-1">Water Year</Form.Label>
              <Form.Select
                size="sm"
                value={selectedWaterYear ?? ''}
                onChange={(e) => setWaterYearPreference(e.target.value || null)}
                disabled={quarters.isLoading || temporalOptions.availableWaterYears.length === 0}
              >
                {temporalOptions.availableWaterYears.map((waterYear) => (
                  <option key={waterYear} value={waterYear}>
                    {waterYear}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>

            <Form.Group className="flex-grow-1" style={{ maxWidth: '150px' }}>
              <Form.Label className="small fw-bold mb-1">Month</Form.Label>
              <Form.Select
                size="sm"
                value={selectedMonth ?? ''}
                onChange={(e) => setMonthPreference(e.target.value || null)}
                disabled={quarters.isLoading || availableMonths.length === 0}
              >
                {availableMonths.map((month) => (
                  <option key={monthKey(month.monthNumber)} value={monthKey(month.monthNumber)}>
                    {month.monthName}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>
          </div>
        </div>

        {!selectedLocation ? (
          <div className="d-flex align-items-center justify-content-center flex-grow-1 text-muted">
            <div className="text-center">
              <div style={{ fontSize: '3rem' }}>📍</div>
              <h5>Select a Location</h5>
              <p>Click on a location on the map to view its time series data.</p>
            </div>
          </div>
        ) : primary.isLoading || secondary.isLoading ? (
          <div className="d-flex justify-content-center align-items-center flex-grow-1">
            <div className="text-center">
              <Spinner animation="border" variant="primary" />
              <div className="mt-2 small text-muted">Loading timeseries data...</div>
            </div>
          </div>
        ) : (
          <>
            {hasData ? (
              <div className="flex-grow-1 p-2" style={{ overflow: 'hidden', minHeight: 0 }}>
                <PlotlyChart
                  selectedLocation={selectedLocation}
                  primaryData={primaryData}
                  secondaryData={secondaryData}
                  height="100%"
                  allowForecastSelect={true}
                  showLegend={false}
                />
              </div>
            ) : (
              <div className="d-flex align-items-center justify-content-center flex-grow-1">
                <div className="text-center text-muted">
                  <div style={{ fontSize: '2rem' }}>📊</div>
                  <h6>No Data Available</h6>
                  <p className="small">
                    Try switching to Filters to adjust the time range or check if data exists for
                    this location.
                  </p>
                </div>
              </div>
            )}
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default NwmdTimeseriesPlot;
