import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { DashboardProvider } from './context/DashboardContext.jsx';
import Home from './components/Home.jsx';
import Dashboard from './components/Dashboard.jsx';
import Navbar from './components/Navbar.jsx';
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
            <Route 
              path="/dashboard" 
              element={
                  <DashboardProvider>
                    <Dashboard />
                  </DashboardProvider>
              } 
            />
            {/* Future routes */}
            <Route 
              path="/forecast" 
              element={
                <div className="container mt-5 text-center">
                  <h2>Forecast Analysis</h2>
                  <p className="text-muted">Coming Soon</p>
                </div>
              } 
            />
            <Route 
              path="/data" 
              element={
                <div className="container mt-5 text-center">
                  <h2>Data Management</h2>
                  <p className="text-muted">Coming Soon</p>
                </div>
              } 
            />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
