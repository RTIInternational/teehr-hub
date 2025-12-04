import React from 'react';
import { useDashboard } from '../context/DashboardContext.jsx';
import { ActionTypes } from '../context/DashboardContext.jsx';
import PlotlyChart from './PlotlyChart.jsx';
import TimeseriesControls from './TimeseriesControls.jsx';

const TimeseriesComponent = () => {
  const { state, dispatch } = useDashboard();
  
  const hasData = state.timeseriesData.primary?.length > 0 || state.timeseriesData.secondary?.length > 0;
  const shouldShowPlot = hasData && !state.timeseriesLoading;
  
  const handleClose = () => {
    dispatch({ type: ActionTypes.SELECT_LOCATION, payload: null });
  };
  
  return (
    <div className="card shadow-lg" style={{ borderRadius: '8px' }}>
      <div className="card-header py-2 d-flex justify-content-between align-items-center">
        <h6 className="card-title mb-0">📍 Location Details</h6>
        <button 
          type="button" 
          className="btn-close" 
          aria-label="Close"
          onClick={handleClose}
        ></button>
      </div>
      <div className="card-body p-3">
        {!state.selectedLocation ? (
          <div className="d-flex align-items-center justify-content-center" style={{ height: '400px' }}>
            <div className="text-center text-muted">
              <div style={{ fontSize: '3rem' }}>📍</div>
              <h5>Select a Location</h5>
              <p>Click on a location on the map to view timeseries data</p>
            </div>
          </div>
        ) : (
          <>
            {/* Location Information - Always shown when location is selected */}
            <div className="mb-3">
              <h6 className="text-primary mb-2">🎯 Selected Location</h6>
              <div className="row g-2 small">
                <div className="col-6">
                  <span className="text-muted">Location ID:</span>
                  <span className="fw-bold ms-1">{state.selectedLocation.location_id}</span>
                </div>
                <div className="col-6">
                  <span className="text-muted">Latitude:</span>
                  <span className="fw-bold ms-1">{state.selectedLocation.coordinates?.[1]?.toFixed(4)}</span>
                </div>
                <div className="col-12">
                  <span className="text-muted">Name:</span>
                  <span className="fw-bold ms-1">{state.selectedLocation.name}</span>
                </div>
                <div className="col-6">
                  <span className="text-muted">Longitude:</span>
                  <span className="fw-bold ms-1">{state.selectedLocation.coordinates?.[0]?.toFixed(4)}</span>
                </div>
              </div>
            </div>
            <hr className="my-3" />
            
            {/* Content Area - Controls or Plot */}
            {state.timeseriesLoading ? (
              <div className="d-flex align-items-center justify-content-center" style={{ height: '400px' }}>
                <div className="text-center">
                  <div className="spinner-border text-primary mb-3" role="status">
                    <span className="visually-hidden">Loading...</span>
                  </div>
                  <h5>Loading Timeseries Data</h5>
                </div>
              </div>
            ) : !shouldShowPlot ? (
              <TimeseriesControls />
            ) : (
              <PlotlyChart 
                primaryData={state.timeseriesData.primary}
                secondaryData={state.timeseriesData.secondary}
                selectedLocation={state.selectedLocation}
                filters={state.timeseriesFilters}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default TimeseriesComponent;