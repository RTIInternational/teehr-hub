import { Container, Row, Col, Card, Button, Nav } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth.js';

const Home = () => {
  const { signup } = useAuth();

  return (
    <div className="home-page welcome-page">
      <div className="hero-section welcome-hero text-white py-5">
        <Container>
          <Row className="align-items-center mb-3">
            <Col xs={12} lg={8}>
              <div className="d-flex flex-wrap align-items-center gap-3">
                <Link to="/" aria-label="TEEHR welcome page">
                  <img src="/teehr.png" alt="TEEHR logo" className="welcome-logo" />
                </Link>
                <img
                  src="https://raw.githubusercontent.com/RTIInternational/teehr/main/docs/images/readme/CIROHLogo_200x200.png"
                  alt="CIROH logo"
                  className="welcome-ciroh-logo"
                />
              </div>
            </Col>
            <Col xs={12} lg={4} className="mt-3 mt-lg-0">
              <div className="d-grid gap-2 d-sm-flex justify-content-lg-end">
                <Button
                  variant="success"
                  onClick={() => signup(`${window.location.origin}/hub`)}
                >
                  Sign Up for Dashboards
                </Button>
                <Button
                  as="a"
                  href="mailto:ciroh.teehr@gmail.com"
                  variant="outline-light"
                >
                  Request Access
                </Button>
              </div>
            </Col>
          </Row>

          <Row className="mb-4">
            <Col>
              <Nav className="welcome-link-nav flex-wrap" variant="pills">
                <Nav.Item>
                  <Nav.Link as={Link} to="/hub">Dashboard Hub</Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link href="https://github.com/RTIInternational/teehr" target="_blank" rel="noreferrer">TEEHR-Python Repo</Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link href="https://github.com/RTIInternational/teehr-hub" target="_blank" rel="noreferrer">TEEHR-Hub Repo</Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link href="https://hub.teehr.rtiamanzi.org/hub/spawn" target="_blank" rel="noreferrer">TEEHR-Hub Deployment</Nav.Link>
                </Nav.Item>
              </Nav>
            </Col>
          </Row>

          <Row className="justify-content-center text-center">
            <Col lg={10}>
              <h1 className="display-4 mb-3">Welcome to TEEHR-Cloud</h1>
              <p className="lead mb-0">
                Facilitating continental-scale evaluation of historical and real-time hydrologic data at scale.
              </p>
            </Col>
          </Row>
        </Container>
      </div>

      <Container className="py-4 py-lg-5">
        <Row>
          <Col lg={10} className="mx-auto">
            <Card className="shadow-sm border-0">
              <Card.Body className="p-4 p-lg-5">
                <h3 className="mb-3">The TEEHR-Cloud Framework</h3>
                <p className="text-muted mb-4">
                  TEEHR-Cloud connects data pipelines, warehouse infrastructure, and analysis interfaces so hydrologic teams can evaluate historical simulations and real-time forecasts in one coordinated ecosystem.
                </p>

                <section className="mb-4">
                  <h4 className="h5 mb-2">1. Framework Overview</h4>
                  <p className="mb-0">
                    The framework combines the TEEHR-Python package, cloud infrastructure, and user-facing tools to support end-to-end evaluation workflows. This includes transforming heterogeneous data sources into consistent schemas, enabling reproducible analysis, and delivering results through notebooks and dashboards.
                  </p>
                </section>

                <section className="mb-4">
                  <h4 className="h5 mb-2">2. Data Warehouse</h4>
                  <p className="mb-0">
                    The warehouse is the core integration layer for model, observation, and derived evaluation products. It enables scalable storage, query performance for continental datasets, and standardized access patterns used across notebooks, services, and dashboards.
                  </p>
                </section>

                <section>
                  <h4 className="h5 mb-2">3. Services and Evaluation Manager</h4>
                  <p className="mb-0">
                    Platform services orchestrate workflows and expose analysis capabilities. The Evaluation Manager pattern organizes repeatable evaluation runs, tracks configurations, and helps teams compare methods and outcomes with greater transparency.
                  </p>
                </section>
              </Card.Body>
            </Card>
          </Col>
        </Row>

        <Row className="mt-4 pb-4">
          <Col lg={10} className="mx-auto">
            <table className="table table-borderless align-middle welcome-funding-table mb-0">
              <tbody>
                <tr>
                  <td className="welcome-funding-logo-cell">
                    <img
                      src="https://github.com/RTIInternational/teehr/blob/main/docs/images/readme/CIROHLogo_200x200.png?raw=true"
                      alt="CIROH logo"
                      className="welcome-funding-logo"
                    />
                  </td>
                  <td>
                    Funding for this project was provided by the National Oceanic & Atmospheric Administration (NOAA), awarded to the Cooperative Institute for Research to Operations in Hydrology (CIROH) through the NOAA Cooperative Agreement with The University of Alabama (NA22NWS4320003).
                  </td>
                </tr>
              </tbody>
            </table>
          </Col>
        </Row>
      </Container>
    </div>
  );
};

export default Home;