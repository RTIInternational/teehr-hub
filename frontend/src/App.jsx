import { Container, Alert } from 'react-bootstrap';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard.jsx';
import Home from './components/Home.jsx';
import Navbar from './components/Navbar.jsx';
import { DashboardProvider } from './context/DashboardContext.jsx';
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
                <Container className="mt-5 text-center">
                  <Alert variant="info">
                    <Alert.Heading>Forecast Analysis</Alert.Heading>
                    <p>Coming Soon</p>
                  </Alert>
                </Container>
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
