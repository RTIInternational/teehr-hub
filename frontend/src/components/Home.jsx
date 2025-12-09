import { Container, Row, Col, Card, Button } from 'react-bootstrap';
import { Link } from 'react-router-dom';

const Home = () => {
  const dashboards = [
    {
      id: 'retrospective-simulations',
      title: 'Retrospective Simulations',
      description: 'Analyze and compare historical simulation data with observed values. Explore metrics, timeseries, and spatial patterns.',
      features: [
        'Interactive maps with simulation metrics',
        'Time series visualization and comparison',
        'Statistical performance metrics',
        'Multi-configuration analysis'
      ],
      path: '/dashboard',
      status: 'available',
      image: '/api/static/preview-retrospective.png', // placeholder
      color: 'primary'
    },
    // Future dashboards can be added here
    {
      id: 'forecast-analysis',
      title: 'Forecast Analysis',
      description: 'Real-time forecast analysis and validation tools for operational and research data streams.',
      features: [
        'Live forecast data',
        'Forecast vs observation comparison',
        'Lead time analysis'
      ],
      path: '/forecast',
      status: 'available',
      image: '/api/static/preview-forecast.png', // placeholder
      color: 'secondary'
    },

    {
      id: 'data-management',
      title: 'Data Management',
      description: 'Manage and upload simulation and observation datasets.',
      features: [
        'Data upload and validation',
        'Dataset metadata management',
        'Quality control tools'
      ],
      path: '/data',
      status: 'coming-soon',
      image: '/api/static/preview-data.png', // placeholder
      color: 'success'
    },

    {
      id: 'retrospective-model-comparisons',
      title: 'Retrospective Model Comparisons',
      description: 'Evaluate multiple historical simulations compared to a baseline, considering sampling uncertainty.',
      features: [
        'Probability of improvement of alternative models over a baseline.',
        'Interactive maps, heatmaps and plots',
        'Aggregated and detailed summaries',
        'Filter by physical, geographical, temporal or hydrologic attributes to see trends'
      ],
      path: '/retrospective-model-comparisons',
      status: 'coming-soon',
      image: '/api/static/preview-data.png', // placeholder
      color: 'primary'
    },

    {
      id: 'forecast-flood-protection',
      title: 'Deterministic Forecast Evaluation for Flood Protection',
      description: 'Evaluate deterministic forecasts for flood protection applications.',
      features: [
        'Event-based evaluation',
        'Evaluate event peak and timing',
        'Categorical metrics',
        'Variable flood thresholds',
        'Interactive maps and plots',
        'Warning and lead time assessments',
        'Sampling uncertainty estimated'
      ],
      path: '/forecast-flood-protection',
      status: 'coming-soon',
      image: '/api/static/preview-data.png', // placeholder
      color: 'secondary'
    },

    {
      id: 'forecast-water-supply',
      title: 'Ensemble Forecast Evaluation for Water Supply',
      description: 'Evaluate ensemble forecasts for water supply applications.',
      features: [
        'Continuous and seasonal evaluation',
        'Ensemble metrics',
        'Evaluate low flows, low flow duration',
        'Variable low flow thresholds',
        'Interactive maps and plots',
        'Filter by physical, geographical, temporal or hydrologic attributes to see trends',
        'Sampling uncertainty estimated'
      ],
      path: '/forecast-water-supply',
      status: 'coming-soon',
      image: '/api/static/preview-data.png', // placeholder
      color: 'success'
    },
    
    {
      id: 'post-event',
      title: 'Post Flood Event Evaluations',
      description: 'Evaluate ensemble forecasts for water supply applications.',
      features: [
        'Interactive precipitation and streamflow error maps',
        'Spaghetti plots of streamflow forecasts with associated precipitation forecasts',
        'Cycle by cycle error heatmaps',
        'Cycle by cycle time series plots highlighting warning time'
      ],
      path: '/post-event',
      status: 'coming-soon',
      image: '/api/static/preview-data.png', // placeholder
      color: 'primary'
    },

    {
      id: 'deterministic-forecast-dam-safety',
      title: 'Deterministic Forecast Evaluation for Dam Safety and Hydropower',
      description: 'Real-time forecast analysis for dam safety and hydropower applications.',
      features: [
        'Check back later for details',
      ],
      path: '/forecast',
      status: 'coming-soon',
      image: '/api/static/preview-forecast.png', // placeholder
      color: 'secondary'
    },

    {
      id: 'deterministic-forecast-water-supply',
      title: 'Deterministic Forecast Evaluation for Water Supply',
      description: 'Real-time forecast analysis for water supply applications.',
      features: [
        'Check back later for details',
      ],
      path: '/data',
      status: 'coming-soon',
      image: '/api/static/preview-data.png', // placeholder
      color: 'success'
    },

  ];

  const getCardComponent = (dashboard) => {
    if (dashboard.status === 'available') {
      return (
        <Link to={dashboard.path} style={{ textDecoration: 'none' }}>
          <Card className="h-100 dashboard-card dashboard-card-available" style={{ cursor: 'pointer' }}>
            <Card.Header className={`bg-${dashboard.color} text-white`}>
              <Card.Title className="mb-0">{dashboard.title}</Card.Title>
            </Card.Header>
            <Card.Body className="d-flex flex-column">
              <Card.Text>{dashboard.description}</Card.Text>
              <div className="features-list mb-3">
                <strong>Features:</strong>
                <ul className="mt-2">
                  {dashboard.features.map((feature, idx) => (
                    <li key={idx}>{feature}</li>
                  ))}
                </ul>
              </div>
              <div className="mt-auto">
                <Button variant={dashboard.color} className="w-100">
                  Open Dashboard
                </Button>
              </div>
            </Card.Body>
          </Card>
        </Link>
      );
    } else {
      return (
        <Card className="h-100 dashboard-card dashboard-card-disabled">
          <Card.Header className={`bg-${dashboard.color} text-white opacity-75`}>
            <Card.Title className="mb-0">
              {dashboard.title}
              <span className="badge bg-warning text-dark ms-2">Coming Soon</span>
            </Card.Title>
          </Card.Header>
          <Card.Body className="d-flex flex-column">
            <Card.Text className="text-muted">{dashboard.description}</Card.Text>
            <div className="features-list mb-3">
              <strong className="text-muted">Planned Features:</strong>
              <ul className="mt-2 text-muted">
                {dashboard.features.map((feature, idx) => (
                  <li key={idx}>{feature}</li>
                ))}
              </ul>
            </div>
            <div className="mt-auto">
              <Button variant="outline-secondary" disabled className="w-100">
                Coming Soon
              </Button>
            </div>
          </Card.Body>
        </Card>
      );
    }
  };

  return (
    <div className="home-page">
      {/* Hero Section */}
      <div className="hero-section bg-primary text-white py-5 mb-4">
        <Container>
          <Row className="justify-content-center text-center">
            <Col lg={8}>
              <h1 className="display-4 mb-3">TEEHR Dashboard Hub</h1>
              <p className="lead">
                Tools for Exploratory Evaluation in Hydrologic Research. 
                Choose from our collection of specialized dashboards for hydrologic data analysis.
              </p>
            </Col>
          </Row>
        </Container>
      </div>

      {/* Dashboard Cards */}
      <Container>
        <Row className="mb-4">
          <Col>
            <h2 className="text-center mb-4">Available Dashboards</h2>
          </Col>
        </Row>
        <Row className="g-4">
          {dashboards.map((dashboard) => (
            <Col key={dashboard.id} lg={4} md={6} sm={12}>
              {getCardComponent(dashboard)}
            </Col>
          ))}
        </Row>
        
        {/* Footer Info */}
        <Row className="mt-5 pt-4 border-top">
          <Col className="text-center text-muted">
            <p>
              <strong>TEEHR</strong> - Tools for Exploratory Evaluation in Hydrologic Research.
            </p>
          </Col>
        </Row>
      </Container>
    </div>
  );
};

export default Home;