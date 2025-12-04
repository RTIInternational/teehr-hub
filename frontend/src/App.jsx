import React from 'react';
import { DashboardProvider } from './context/DashboardContext.jsx';
import Dashboard from './components/Dashboard.jsx';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

function App() {
  return (
    <DashboardProvider>
      <Dashboard />
    </DashboardProvider>
  );
}

export default App;
