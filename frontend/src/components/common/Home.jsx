import { Container, Row, Col, Card, Accordion } from 'react-bootstrap';
import teehrCloudVennDiagram from '../../assets/teehr-cloud-venn-diagram.png';
import teehrIcebergDiagram from '../../assets/data-model-iceberg.png';
import teehrCloudServicesDiagram from '../../assets/cloud-services-image.png';
import teehrDashboardsDiagram from '../../assets/dashboard-snippet-image.png';

const Home = () => {
  return (
    <div className="home-page bg-preset-hydro">
      <div className="hero-section welcome-hero text-white py-5">
        <Container>
          <Row className="justify-content-center text-center">
            <Col lg={10}>
              <h1 className="display-4 mb-3">Welcome to TEEHR-Cloud</h1>
              <p className="lead mb-0">
                Facilitating continental-scale evaluation of historical and real-time hydrologic data.
              </p>
            </Col>
          </Row>
        </Container>
      </div>

      <div className="welcome-main-content">
        <Container className="py-4 py-lg-5">
          <Row>
            <Col lg={10} className="mx-auto">
              <Card className="shadow-sm border-0">
                <Card.Body className="p-4 p-lg-5">
                <h3 className="mb-3">The TEEHR-Cloud Framework</h3>
                <p className="text-muted mb-4">
                  TEEHR-Cloud (Tools for Exploratory Evaluation in Hydrologic Research) is a cloud-based Evaluation Platform that supports standardized evaluations and provides “evaluation-ready” datasets, dashboards, and analytics capabilities.
                </p>

                <Accordion className="mb-2">
                  <Accordion.Item eventKey="overview">
                    <Accordion.Header>Overview</Accordion.Header>
                    <Accordion.Body>
                      <p className="mb-0">
                        The framework combines the TEEHR-Python package, cloud infrastructure, and user-facing tools to support end-to-end evaluation workflows. This includes transforming heterogeneous data sources into consistent schemas, enabling reproducible analysis, and delivering results through notebooks and dashboards.
                      </p>
                      <div className="text-center mt-3">
                        <img
                          src={teehrCloudVennDiagram}
                          alt="TEEHR-Cloud Venn diagram"
                          className="img-fluid welcome-overview-diagram"
                        />
                      </div>
                    </Accordion.Body>
                  </Accordion.Item>

                  <Accordion.Item eventKey="teehr-python">
                    <Accordion.Header>TEEHR-Python Package</Accordion.Header>
                    <Accordion.Body>
                      <p className="mb-3">
                        The TEEHR-Python package provides the core functionality for data processing, analysis, and evaluation. It includes modules for fetching USGS and National Water Model data from external sources, downloading data from the TEEHR data warehouse, validating and loading data into a local or remote warehouse, and performing advanced analytics at scale by leveraging Apache Spark's distributed computing frameworks.
                      </p>
                      <table className="table table-bordered align-middle mb-0">
                        <tbody>
                          <tr>
                            <td>
                              <img
                                src="https://github.com/RTIInternational/teehr/blob/main/docs/images/readme/fetching-and-loading.png?raw=true"
                                alt="Fetching and Loading"
                                className="welcome-teehr-python-image"
                              />
                            </td>
                            <td>
                              <strong>Fetching and Loading</strong> - Tools to bring external or local data into your Evaluation from a variety of sources and file formats.
                            </td>
                          </tr>
                          <tr>
                            <td>
                              <img
                                src="https://github.com/RTIInternational/teehr/blob/main/docs/images/readme/data-validation-and-storage.png?raw=true"
                                alt="Data Validation and Storage"
                                className="welcome-teehr-python-image"
                              />
                            </td>
                            <td>
                              <strong>Data Validation and Storage</strong> - TEEHR's data model helps ensure consistency in field values and types, and interfaces with Apache Iceberg for underlying data storage functionality.
                            </td>
                          </tr>
                          <tr>
                            <td>
                              <img
                                src="https://github.com/RTIInternational/teehr/blob/main/docs/images/readme/analytics.png?raw=true"
                                alt="Analytics"
                                className="welcome-teehr-python-image"
                              />
                            </td>
                            <td>
                              <strong>Analytics</strong> - TEEHR contains a suite of robust and scalable analytic methods that enable users to fully interrogate their datasets.
                            </td>
                          </tr>
                        </tbody>
                      </table>
                      <p className="mt-3 mb-2">
                        <a
                          href="https://rtiinternational.github.io/teehr"
                          target="_blank"
                          rel="noreferrer"
                          className="d-inline-flex align-items-center gap-2 text-decoration-none mb-2"
                          aria-label="TEEHR-Python documentation"
                        >
                          <img
                            src="/favicon.png"
                            alt="TEEHR logo"
                            width="20"
                            height="20"
                          />
                          <span>TEEHR-Python Documentation</span>
                        </a>
                      </p>
                      <p className="mb-2">
                        <a
                          href="https://github.com/RTIInternational/teehr"
                          target="_blank"
                          rel="noreferrer"
                          className="d-inline-flex align-items-center gap-2 text-decoration-none"
                          aria-label="TEEHR repository documentation on GitHub"
                        >
                          <img
                            src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
                            alt="GitHub logo"
                            width="20"
                            height="20"
                          />
                          <span>TEEHR-Python on GitHub</span>
                        </a>
                      </p>
                    </Accordion.Body>
                  </Accordion.Item>

                  <Accordion.Item eventKey="data-warehouse">
                    <Accordion.Header>Data Warehouse</Accordion.Header>
                    <Accordion.Body>
                      <p className="mb-0">
                        The TEEHR data warehouse is the core data layer for model, observation, and derived "Evaluation-Ready" products. Built on Apache Iceberg, it enables scalable storage, query performance for continental datasets, and standardized access patterns used across notebooks, services, and dashboards.
                      </p>
                      <div className="text-center mt-3">
                        <img
                          src={teehrIcebergDiagram}
                          alt="TEEHR Data Warehouse Diagram"
                          className="img-fluid welcome-iceberg-diagram"
                        />
                      </div>
                      <p className="mb-0">
                        The warehouse contains an ever-expanding list of historical and real-time hydrologic datasets including, but not limited to:
                      </p>
                      <ul>
                        <li>The National Water Model (NWM) v3.0 hourly retrospective streamflow and accompanying USGS gage observations at over 8,000 gage locations across the US</li>
                        <li>The National Water Model (NWM) v3.0 hourly retrospective rainfall and temperature summarized to USGS drainage basins across the US</li>
                        <li>Historical research simulations</li>
                        <li>CIROH's <a href="https://hub.ciroh.org/blog/nextgen-research-datastream-april-2026/">Nextgen Research Datastream forecasts</a></li>
                        <li><a href="https://water.noaa.gov/">National Water Prediction Service (NWPS)</a> River Forecast Center streamflow forecasts </li>
                        <li>NWM v3.0 analysis, short-range, and medium-range streamflow forecasts for CONUS and OCONUS locations in near real-time</li>
                        <li>NWM v3.0 analysis, short-range, and medium-range streamflow rainrate forecasts summarized to CONUS and OCONUS USGS drainage basins in near real-time</li>
                      </ul>
                      <p className="mb-0">
                        In addition to simulated and observed hydrologic data, the warehouse also contains tables storing historical and regularly-updated performance metrics and other tables supporting the <a href="https://dashboards.teehr.rtiamanzi.org/">TEEHR Dashboards</a>.
                      </p>
                    </Accordion.Body>
                  </Accordion.Item>

                  <Accordion.Item eventKey="services">
                    <Accordion.Header>Services and Evaluation Manager</Accordion.Header>
                    <Accordion.Body>
                      <p className="mb-0">
                        A suite of cloud-based services regularly ingests data, updates performance metrics, supports data warehouse access and notebook-based interactions, and hosts the <a href="https://dashboards.teehr.rtiamanzi.org/">TEEHR Dashboards</a>.
                      </p>
                      <div className="text-center mt-3">
                        <img
                          src={teehrCloudServicesDiagram}
                          alt="TEEHR Cloud Services Diagram"
                          className="img-fluid welcome-services-diagram"
                        />
                      </div>
                      <p className="mt-3 mb-2">
                        <a
                          href="https://github.com/RTIInternational/teehr-hub"
                          target="_blank"
                          rel="noreferrer"
                          className="d-inline-flex align-items-center gap-2 text-decoration-none"
                          aria-label="TEEHR Cloud Infrastructure repository on GitHub"
                        >
                          <img
                            src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
                            alt="GitHub logo"
                            width="20"
                            height="20"
                          />
                          <span>TEEHR-Cloud Infrastructure on GitHub</span>
                        </a>
                      </p>
                    </Accordion.Body>
                  </Accordion.Item>

                  <Accordion.Item eventKey="dashboards">
                    <Accordion.Header>TEEHR Dashboards</Accordion.Header>
                    <Accordion.Body>
                      <p className="mb-0">
                        Purpose-built <a href="https://dashboards.teehr.rtiamanzi.org/">dashboards</a> deliver interactive performance visualizations and data exploration tools to support evaluation of historical simulations and real-time forecasts from specific perspectives and use-cases.
                      </p>
                      <div className="text-center mt-3">
                        <img
                          src={teehrDashboardsDiagram}
                          alt="TEEHR Dashboards Diagram"
                          className="img-fluid welcome-dashboards-diagram"
                        />
                      </div>
                    </Accordion.Body>
                  </Accordion.Item>

                </Accordion>
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

          <Row className="mt-5 pt-4">
            <Col className="text-center text-muted">
              <p>
                <strong>TEEHR</strong> - Tools for Exploratory Evaluation in Hydrologic Research.
              </p>
            </Col>
          </Row>
        </Container>
      </div>
    </div>
  );
};

export default Home;