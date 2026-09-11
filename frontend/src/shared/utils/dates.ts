export type ParsedQuarter = {
  quarter: string;
  year: number;
  quarterNum: 1 | 2 | 3 | 4;
};

export type WaterYearMonthOption = {
  waterYear: string;
  monthNumber: number;
  monthName: string;
  calendarYear: number;
};

const WATER_YEAR_MONTH_ORDER = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9] as const;

const MONTH_NAME_BY_NUMBER: Record<number, string> = {
  1: 'January',
  2: 'February',
  3: 'March',
  4: 'April',
  5: 'May',
  6: 'June',
  7: 'July',
  8: 'August',
  9: 'September',
  10: 'October',
  11: 'November',
  12: 'December',
};

const QUARTER_TO_MONTHS: Record<1 | 2 | 3 | 4, [number, number, number]> = {
  1: [1, 2, 3],
  2: [4, 5, 6],
  3: [7, 8, 9],
  4: [10, 11, 12],
};

const monthSortRank = (monthNumber: number) => {
  const idx = WATER_YEAR_MONTH_ORDER.indexOf(
    monthNumber as (typeof WATER_YEAR_MONTH_ORDER)[number]
  );
  return idx < 0 ? Number.MAX_SAFE_INTEGER : idx;
};

export const getWaterYearForCalendarMonth = (calendarYear: number, monthNumber: number) => {
  return monthNumber >= 10 ? calendarYear + 1 : calendarYear;
};

export const parseQuarterValue = (quarter: string): ParsedQuarter | null => {
  if (!quarter) return null;

  const normalized = quarter.trim().replace('_', '-');
  const match = normalized.match(/^(\d{4})-Q([1-4])$/);
  if (!match) return null;

  const year = Number.parseInt(match[1], 10);
  const quarterNum = Number.parseInt(match[2], 10) as 1 | 2 | 3 | 4;

  if (!Number.isFinite(year)) return null;

  return {
    quarter: `${year}-Q${quarterNum}`,
    year,
    quarterNum,
  };
};

export const getWaterYearMonthOptionsFromQuarters = (
  quarters: Array<string | null | undefined>
): WaterYearMonthOption[] => {
  const unique = new Map<string, WaterYearMonthOption>();

  (quarters || []).forEach((value) => {
    if (typeof value !== 'string') return;

    const parsed = parseQuarterValue(value);
    if (!parsed) return;

    const months = QUARTER_TO_MONTHS[parsed.quarterNum];
    months.forEach((monthNumber) => {
      const calendarYear = parsed.year;
      const waterYear = String(getWaterYearForCalendarMonth(calendarYear, monthNumber));
      const monthName = MONTH_NAME_BY_NUMBER[monthNumber];

      if (!monthName) return;

      const key = `${waterYear}-${monthNumber}`;
      if (!unique.has(key)) {
        unique.set(key, {
          waterYear,
          monthNumber,
          monthName,
          calendarYear,
        });
      }
    });
  });

  return [...unique.values()];
};

export const deriveWaterYearsFromMonthOptions = (options: WaterYearMonthOption[]) => {
  const years = [...new Set(options.map((item) => item.waterYear))];
  return years.sort((a, b) => Number(b) - Number(a));
};

export const filterWaterYearMonthOptions = (
  options: WaterYearMonthOption[],
  constraints: {
    mapWaterYear?: string | null;
    mapQuarter?: string | null;
    selectedWaterYear?: string | null;
  }
) => {
  const parsedQuarter =
    typeof constraints.mapQuarter === 'string' ? parseQuarterValue(constraints.mapQuarter) : null;

  const quarterMonths = parsedQuarter ? new Set(QUARTER_TO_MONTHS[parsedQuarter.quarterNum]) : null;

  const quarterWaterYear = parsedQuarter
    ? String(parsedQuarter.quarterNum === 4 ? parsedQuarter.year + 1 : parsedQuarter.year)
    : null;

  const constrained = options.filter((item) => {
    if (constraints.mapWaterYear != null && item.waterYear !== constraints.mapWaterYear) {
      return false;
    }

    if (quarterMonths && !quarterMonths.has(item.monthNumber)) {
      return false;
    }

    if (quarterWaterYear && item.waterYear !== quarterWaterYear) {
      return false;
    }

    return true;
  });

  const effectiveWaterYear = constraints.selectedWaterYear ?? constraints.mapWaterYear ?? null;

  const monthsForWaterYear = constrained
    .filter((item) => !effectiveWaterYear || item.waterYear === effectiveWaterYear)
    .toSorted((a, b) => monthSortRank(a.monthNumber) - monthSortRank(b.monthNumber));

  return {
    constrained,
    monthsForWaterYear,
    availableWaterYears: deriveWaterYearsFromMonthOptions(constrained),
  };
};

export const getMonthDateRangeFromWaterYearMonth = (waterYear: string, monthNumber: number) => {
  const wy = Number.parseInt(waterYear, 10);
  if (!Number.isFinite(wy) || monthNumber < 1 || monthNumber > 12) return null;

  const calendarYear = monthNumber >= 10 ? wy - 1 : wy;
  const startDate = new Date(calendarYear, monthNumber - 1, 1);
  startDate.setHours(0, 0, 0, 0);

  const endDate = new Date(calendarYear, monthNumber, 0);
  endDate.setHours(23, 59, 0, 0);

  return {
    start_date: startDate.toISOString().slice(0, 16),
    end_date: endDate.toISOString().slice(0, 16),
  };
};
