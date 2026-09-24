import DashboardPanel from '@/shared/components/DashboardPanel';
import type { PolygonFeatureProps, PolygonFeatures } from '@/shared/types/gridded/tiles';

import { useDashboard, ActionTypes } from '../DashboardContext';

// Attribute columns are driven by the pmtiles archive, so render whatever the
// features carry rather than hard-coding a schema. `id` leads since it is the
// key a warehouse query is built on.
const orderedKeys = (features: PolygonFeatures) => {
  const keys = new Set();
  features.forEach((props) => Object.keys(props || {}).forEach((k) => keys.add(k)));
  keys.delete('id');
  return ['id', ...Array.from(keys)];
};

const GriddedPolygonPanel = () => {
  const { state, dispatch } = useDashboard();
  const { polygonFeatures, polygonClickLngLat, selectedLocation, activePolygonLayer } = state;

  const selectedId = selectedLocation?.primary_location_id ?? null;

  const selectFeature = (props: PolygonFeatureProps) => {
    dispatch({
      type: ActionTypes.SELECT_LOCATION,
      payload: {
        // Named to match the other dashboards so LocationCard and apiService
        // calls work against this object unchanged.
        primary_location_id: props.id,
        name: props.name,
        coordinates: polygonClickLngLat ? [polygonClickLngLat.lon, polygonClickLngLat.lat] : null,
      },
    });
  };

  const header = (
    <div className="d-flex justify-content-between align-items-center">
      <span className="fw-semibold" style={{ fontSize: '0.9rem' }}>
        📐 Polygon Attributes
        {polygonFeatures.length > 0 && (
          <span className="text-muted fw-normal ms-2" style={{ fontSize: '0.8rem' }}>
            {polygonFeatures.length} at this location
          </span>
        )}
      </span>
      {polygonFeatures.length > 0 && (
        <button
          type="button"
          className="btn-close"
          aria-label="Clear polygon selection"
          onClick={() => dispatch({ type: ActionTypes.CLEAR_POLYGON_FEATURES })}
        />
      )}
    </div>
  );

  if (polygonFeatures.length === 0) {
    return (
      <DashboardPanel header={header} style={{ height: '100%' }}>
        <div className="d-flex align-items-center justify-content-center h-100 text-muted">
          <div className="text-center">
            <div style={{ fontSize: '2rem' }}>📐</div>
            <h6>Polygon Attributes</h6>
            <p className="small mb-0">
              {activePolygonLayer
                ? 'Click a polygon on the map to list every polygon at that location.'
                : 'Enable a polygon layer, then click the map.'}
            </p>
          </div>
        </div>
      </DashboardPanel>
    );
  }

  const columns = orderedKeys(polygonFeatures);

  return (
    <DashboardPanel
      header={header}
      style={{ height: '100%' }}
      bodyStyle={{ padding: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}
    >
      <div style={{ flex: '1 1 auto', minHeight: 0, overflow: 'auto' }}>
        <table className="table table-sm table-hover mb-0" style={{ fontSize: '0.8rem' }}>
          <thead className="table-light" style={{ position: 'sticky', top: 0, zIndex: 1 }}>
            <tr>
              {columns.map((key) => {
                if (typeof key === 'string' || typeof key === 'number') {
                  return (
                    <th key={key} scope="col" className="text-nowrap">
                      {key}
                    </th>
                  );
                }
              })}
            </tr>
          </thead>
          <tbody>
            {polygonFeatures.map((props) => {
              const isSelected = selectedId != null && props.id === selectedId;
              return (
                <tr
                  key={props.id}
                  onClick={() => selectFeature(props)}
                  className={isSelected ? 'table-primary' : ''}
                  style={{ cursor: 'pointer' }}
                >
                  {columns.map((key) => {
                    if (typeof key === 'string' || typeof key === 'number') {
                      return (
                        <td key={key} className="text-nowrap">
                          {props[key] !== null && props[key] !== undefined
                            ? String(props[key] as string | number | boolean)
                            : 'N/A'}
                        </td>
                      );
                    }
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="border-top px-3 py-2 d-flex justify-content-between align-items-center gap-2">
        <span className="small text-muted text-truncate">
          {selectedLocation
            ? `Selected: ${selectedLocation.primary_location_id}`
            : 'Select a row to choose a location'}
        </span>
        <button
          type="button"
          className="btn btn-sm btn-primary text-nowrap"
          disabled={!selectedLocation}
          // TODO: wire to the iceberg warehouse via apiService.getPrimaryTimeseries
          onClick={() => {}}
        >
          Load Timeseries
        </button>
      </div>
    </DashboardPanel>
  );
};

export default GriddedPolygonPanel;
