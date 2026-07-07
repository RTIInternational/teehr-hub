import { useEffect } from "react";
import { Card, Spinner, Row, Col, Badge, ListGroup } from "react-bootstrap";

const getUsTimezoneRegion = (timezone) => {
  if (!timezone) return null;

  if (timezone.includes("New_York")) return "Eastern";
  if (timezone.includes("Chicago")) return "Central";
  if (timezone.includes("Denver") || timezone.includes("Phoenix")) {
    return "Mountain";
  }
  if (timezone.includes("Los_Angeles")) return "Pacific";

  return null;
};

export const SiteInfo = ({
  selectedLocation,
  metadataLoading,
  metadata,
  loadLocationMetadata,
}) => {
  useEffect(() => {
    const id = selectedLocation?.primary_location_id;
    if (!id) return;

    loadLocationMetadata(id);
  }, [loadLocationMetadata, selectedLocation?.primary_location_id]);

  return (
    <Card
      className="shadow-lg h-100 d-flex flex-column"
      style={{ borderRadius: "8px" }}
    >
      <Card.Body className="p-0 d-flex flex-column flex-grow-1 overflow-hidden">
        {!selectedLocation ? (
          <div className="d-flex align-items-center justify-content-center flex-grow-1 text-muted">
            <div className="text-center">
              <div style={{ fontSize: "3rem" }}>📍</div>
              <h5>Select a Location</h5>
              <p>Click on a location on the map to view its metadata.</p>
            </div>
          </div>
        ) : metadataLoading ? (
          <div className="d-flex justify-content-center align-items-center flex-grow-1">
            <div className="text-center">
              <Spinner animation="border" variant="primary" />
              <div className="mt-2 small text-muted">
                Loading location metadata...
              </div>
            </div>
          </div>
        ) : metadata ? (
          <div
            className="flex-grow-1 d-flex flex-column"
            style={{ overflow: "auto", minHeight: 0 }}
          >
            <SiteHeader
              locationMetadata={metadata}
              selectedLocation={selectedLocation}
            />
            <SiteDetailsSection locationMetadata={metadata} />
          </div>
        ) : (
          <div className="d-flex align-items-center justify-content-center flex-grow-1">
            <div className="text-center text-muted">
              <div style={{ fontSize: "2rem" }}>📊</div>
              <h6>No Data Available</h6>
              <p className="small">
                No metadata could be retrieved for this location.
              </p>
            </div>
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

const SiteHeader = ({ locationMetadata, selectedLocation }) => {
  const data = locationMetadata?.features?.[0];
  if (!data) return null;

  const primaryIdRaw =
    selectedLocation?.primary_location_id ||
    data.id ||
    data.properties?.id ||
    "";
  const primaryIdValue = String(primaryIdRaw).replace(/^usgs-/i, "");
  const secondaryIdValue = selectedLocation?.secondary_location_id;
  const timezoneRegion = getUsTimezoneRegion(
    data.properties?.timezone || data.properties?.iana_timezone,
  );

  return (
    <div className="border-bottom p-2" style={{ backgroundColor: "#f8f9fa" }}>
      <div className="d-flex justify-content-between align-items-start gap-2">
        <div>
          <h6 className="mb-1 fw-bold text-truncate">{data.properties.name}</h6>
          <div className="d-flex align-items-center gap-1">
            <Badge bg="info" className="fs-8">
              USGS-{primaryIdValue}
            </Badge>
            {secondaryIdValue ? (
              <Badge bg="secondary" className="fs-8">
                {secondaryIdValue}
              </Badge>
            ) : null}
          </div>
        </div>
      </div>
      <small
        className="text-muted d-block"
        style={{ fontSize: "0.75rem", marginTop: "0.25rem" }}
      >
        {data.properties?.state_name || ""}
        {data.properties?.county_name
          ? ` • ${data.properties.county_name}`
          : ""}
        {timezoneRegion ? ` • ${timezoneRegion} Time` : ""}
      </small>
    </div>
  );
};

const SiteDetailsSection = ({ locationMetadata }) => {
  const data = locationMetadata?.features?.[0];
  if (!data) return null;

  const p = data.properties;
  const coords = data.geometry?.coordinates;

  return (
    <div className="p-2 d-flex flex-column overflow-auto">
      <Row className="g-3">
        <Col xs={12} md={6}>
          <div className="h-100 px-1">
            <h6
              className="fw-bold text-uppercase text-muted mb-1"
              style={{ fontSize: "0.68rem", letterSpacing: "0.04em" }}
            >
              Location
            </h6>
            <ListGroup variant="flush" className="small">
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>Lat</span>
                  <span className="fw-bold">{coords?.[1]?.toFixed(4)}</span>
                </div>
              </ListGroup.Item>
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>Lon</span>
                  <span className="fw-bold">{coords?.[0]?.toFixed(4)}</span>
                </div>
              </ListGroup.Item>
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>Elev (m)</span>
                  <span className="fw-bold">{p?.elev_mean_m || "—"}</span>
                </div>
              </ListGroup.Item>
            </ListGroup>
          </div>
        </Col>

        <Col xs={12} md={6}>
          <div className="h-100 px-1">
            <h6
              className="fw-bold text-uppercase text-muted mb-1"
              style={{ fontSize: "0.68rem", letterSpacing: "0.04em" }}
            >
              Hydrology
            </h6>
            <ListGroup variant="flush" className="small">
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>Drain (km²)</span>
                  <span className="fw-bold">{p?.drainage_area_km2 || "—"}</span>
                </div>
              </ListGroup.Item>
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>Q50 (cms)</span>
                  <span className="fw-bold">
                    {p?.q50_cms ? parseFloat(p.q50_cms).toFixed(2) : "—"}
                  </span>
                </div>
              </ListGroup.Item>
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>HUC-12</span>
                  <span className="fw-bold">{p?.huc12?.slice(6) || "—"}</span>
                </div>
              </ListGroup.Item>
            </ListGroup>
          </div>
        </Col>

        <Col xs={12} md={6}>
          <div className="h-100 px-1">
            <h6
              className="fw-bold text-uppercase text-muted mb-1"
              style={{ fontSize: "0.68rem", letterSpacing: "0.04em" }}
            >
              Monitoring
            </h6>
            <ListGroup variant="flush" className="small">
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>First Year</span>
                  <span className="fw-bold">{p?.first_year || "—"}</span>
                </div>
              </ListGroup.Item>
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>Last Year</span>
                  <span className="fw-bold">{p?.last_year || "—"}</span>
                </div>
              </ListGroup.Item>
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>Series Count</span>
                  <span className="fw-bold">{p?.num_timeseries || "—"}</span>
                </div>
              </ListGroup.Item>
            </ListGroup>
          </div>
        </Col>

        <Col xs={12} md={6}>
          <div className="h-100 px-1">
            <h6
              className="fw-bold text-uppercase text-muted mb-1"
              style={{ fontSize: "0.68rem", letterSpacing: "0.04em" }}
            >
              Climate
            </h6>
            <ListGroup variant="flush" className="small">
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>Temp (C)</span>
                  <span className="fw-bold">{p?.temp_mean_c || "—"}</span>
                </div>
              </ListGroup.Item>
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>Precip (mm)</span>
                  <span className="fw-bold">{p?.pcpn_mean_mm || "—"}</span>
                </div>
              </ListGroup.Item>
              <ListGroup.Item
                className="px-0 py-1 border-0"
                style={{ fontSize: "0.85rem" }}
              >
                <div className="d-flex justify-content-between">
                  <span>L2 Ecoregion</span>
                  <span className="fw-bold">{p?.epa_ecoregion_l2 || "—"}</span>
                </div>
              </ListGroup.Item>
            </ListGroup>
          </div>
        </Col>
      </Row>

      {/* USGS Link */}
      <div className="border-top pt-2 mt-2">
        <UsgsLink locationMetadata={locationMetadata} />
      </div>
    </div>
  );
};

const UsgsLink = ({ locationMetadata }) => {
  const siteCode = locationMetadata?.features?.[0]?.id.toUpperCase();
  return (
    <a
      href={`https://waterdata.usgs.gov/monitoring-location/${siteCode}`}
      target="_blank"
      rel="noopener noreferrer"
      className="btn btn-xs btn-outline-primary w-100"
      style={{ fontSize: "0.8rem", padding: "0.25rem 0.5rem" }}
    >
      📊 USGS
    </a>
  );
};
