import { useCallback, useMemo } from 'react';

import type { MapMetric } from '@/shared/types/maps';

import { ActionTypes, useDashboard } from '../DashboardContext';
import { computeCdfData } from '../utils/utils';
import { useFilteredLocations } from './useFilteredLocations';

const useNwmdVisibleLocations = (table: string) => {
  const { state } = useDashboard();
  const locations = useFilteredLocations({ table, ...state.mapFilters });

  const visibleLocations = useMemo(() => {
    const features = locations.data?.features || [];
    const bounds = state.mapViewportBounds;

    if (!bounds) return features;

    const { west, south, east, north } = bounds;
    if (![west, south, east, north].every((value) => Number.isFinite(value))) {
      return features;
    }

    return features.filter((feature) => {
      const coords = feature?.geometry?.coordinates;
      if (!Array.isArray(coords) || coords.length < 2) return false;

      const [lon, lat] = coords;
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) return false;

      // Handle anti-meridian crossing when west > east.
      const inLonRange = west <= east ? lon >= west && lon <= east : lon >= west || lon <= east;

      const inLatRange = lat >= south && lat <= north;
      return inLonRange && inLatRange;
    });
  }, [locations.data, state.mapViewportBounds]);

  return {
    visibleLocations,
  };
};

export const useCdfPlots = () => {
  const { state, dispatch } = useDashboard();

  const setCdfPlotMetric = useCallback(
    (plotId: string, metricName: MapMetric) => {
      dispatch({
        type: ActionTypes.SET_CDF_PLOT_METRIC,
        payload: { plotId: plotId, metricName },
      });
    },
    [dispatch]
  );

  return {
    plotIds: state.cdfPlotOrder,
    setCdfPlotMetric,
  };
};

export const useCdfPlot = (table: string, plotId: string) => {
  const { state } = useDashboard();
  const { visibleLocations } = useNwmdVisibleLocations(table);

  const cdfData = useMemo(() => {
    const metricName = state.cdfPlots?.[plotId]?.metricName || null;
    return metricName ? computeCdfData(visibleLocations, metricName) : [];
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally using primitive metricName to avoid recomputing all plots when any plot changes
  }, [state.cdfPlots?.[plotId]?.metricName, visibleLocations, plotId]);

  const metricName = state.cdfPlots?.[plotId]?.metricName || null;

  return {
    cdfData,
    metricName,
  };
};
