import { useEffect } from 'react';
import { useRetrospectiveDashboard } from '../../../context/RetrospectiveDashboardContext.jsx';
import { useRetrospectiveData } from './useRetrospectiveData';
import MapComponent from './MapComponent.jsx';
import TimeseriesComponent from './TimeseriesComponent.jsx';

const Dashboard = () => {
  const { state } = useRetrospectiveDashboard();
  const { initializeRetrospectiveData } = useRetrospectiveData();
  
  // Debug: Log state changes
  useEffect(() => {
    console.log('Dashboard state updated:', {
      configurationsLength: state.configurations?.length,
      variablesLength: state.variables?.length,
      metricsLength: state.metrics?.length,
      error: state.error
    });
  }, [state.configurations, state.variables, state.metrics, state.error]);
  
  // Load initial data when component mounts
  useEffect(() => {
    const initializeData = async () => {
      try {
        console.log('Dashboard: Starting data initialization...');
        await initializeRetrospectiveData();
        console.log('Dashboard: Data initialization completed');
      } catch (error) {
        console.error('Dashboard: Error during initialization:', error);
      }
    };
    
    initializeData();
  }, [initializeRetrospectiveData]);
  
  return (
    <div className="d-flex flex-column" style={{ height: 'calc(100vh - 56px)' }}>
      {/* Height adjusted for navbar (Bootstrap navbar is typically 56px) */}
      
      <div className="container-fluid flex-grow-1 p-0">
        <div className="row g-0 h-100">
          {/* Main content - full width */}
          <div className="col-12">
            <div className="position-relative h-100">
              {/* Error Alert */}
              {state.error && (
                <div className="alert alert-danger alert-dismissible m-3" role="alert" style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 1000 }}>
                  <i className="bi bi-exclamation-triangle-fill me-2"></i>
                  <strong>Error:</strong> {state.error}
                  <button 
                    type="button" 
                    className="btn-close" 
                    onClick={() => window.location.reload()}
                    aria-label="Close"
                  ></button>
                </div>
              )}
              
              {/* Full-screen map */}
              <div className="h-100">
                <MapComponent />
              </div>
              
              {/* Overlay timeseries card */}
              {state.selectedLocation && (
                <div 
                  className="position-absolute" 
                  style={{ 
                    top: '80px', 
                    right: '20px', 
                    width: '550px', 
                    maxHeight: 'calc(100vh - 216px)', // 56px navbar + 160px original offset
                    zIndex: 1000,
                    overflowY: 'auto'
                  }}
                >
                  <TimeseriesComponent />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;