import { useCallback, useMemo } from "react";
import {
  ActionTypes,
  useNwmdDashboard,
} from "../../../context/NwmdDashboardContext";
import { computeCdfData } from "./utils";

// Derive visible locations from already-filtered locations and current map viewport bounds.
const useNwmdVisibleLocations = () => {
  const { state } = useNwmdDashboard();

  const visibleLocations = useMemo(() => {
    const features = state.locations?.features || [];
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
      const inLonRange =
        west <= east ? lon >= west && lon <= east : lon >= west || lon <= east;

      const inLatRange = lat >= south && lat <= north;
      return inLonRange && inLatRange;
    });
  }, [state.locations, state.mapViewportBounds]);

  return {
    visibleLocations,
  };
};

export const useCdfPlots = () => {
  const { state, dispatch } = useNwmdDashboard();

  const setCdfPlotMetric = useCallback(
    (plotId, metricName) => {
      dispatch({
        type: ActionTypes.SET_CDF_PLOT_METRIC,
        payload: { plotId: plotId, metricName },
      });
    },
    [dispatch],
  );

  return {
    plotIds: state.cdfPlotOrder,
    setCdfPlotMetric,
  };
};

export const useCdfPlot = (plotId) => {
  const { state } = useNwmdDashboard();
  const { visibleLocations } = useNwmdVisibleLocations();

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
