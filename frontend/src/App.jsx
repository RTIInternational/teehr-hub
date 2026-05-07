import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Dashboard } from './components/dashboards/retrospective';
import { ForecastDashboard } from './components/dashboards/forecast';
import { DataDashboard } from './components/dashboards/data_management';
import { Home, Navbar } from './components/common';
import { RetrospectiveDashboardProvider } from './context/RetrospectiveDashboardContext.jsx';
import { ForecastDashboardProvider } from './context/ForecastDashboardContext.jsx';
import { DataDashboardProvider } from './context/DataDashboardContext.jsx';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <Navbar />
        <main>
          <Routes>
            <Route path="/" element={<Home />} />
            {/* Redirect old dashboard route to retrospective */}
            <Route path="/dashboard" element={<Navigate to="/retrospective" replace />} />
            <Route
              path="/retrospective"
              element={
                  <RetrospectiveDashboardProvider>
                    <Dashboard />
                  </RetrospectiveDashboardProvider>
              }
            />
            {/* Future routes */}
            <Route
              path="/forecast"
              element={
                  <ForecastDashboardProvider>
                    <ForecastDashboard />
                  </ForecastDashboardProvider>
              }
            />
            <Route
              path="/data"
              element={
                <DataDashboardProvider>
                  <DataDashboard />
                </DataDashboardProvider>
              }
            />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
