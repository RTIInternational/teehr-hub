import { Container, Alert } from 'react-bootstrap';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Dashboard } from './components/dashboards/retrospective';
import { ForecastDashboard } from './components/dashboards/forecast';
import { Home, Navbar } from './components/common';
import { RetrospectiveDashboardProvider } from './context/RetrospectiveDashboardContext.jsx';
import { ForecastDashboardProvider } from './context/ForecastDashboardContext.jsx';
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
                <Container className="mt-5 text-center">
                  <Alert variant="info">
                    <Alert.Heading>Data Management</Alert.Heading>
                    <p>Coming Soon</p>
                  </Alert>
                </Container>
              } 
            />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
