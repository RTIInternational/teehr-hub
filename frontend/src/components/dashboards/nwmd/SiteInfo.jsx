import { useEffect } from "react";
import { Card, Spinner, Table } from "react-bootstrap";

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
        ) : (
          <>
            {metadata ? (
              <div
                className="flex-grow-1 p-2"
                style={{ overflow: "hidden", minHeight: 0 }}
              >
                <SiteInfoTable locationMetadata={metadata} />
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
          </>
        )}
      </Card.Body>
    </Card>
  );
};

const SiteInfoTable = ({ locationMetadata }) => {
  const data = locationMetadata?.features?.[0];

  if (!data) {
    console.warn(data);
    return;
  }

  return (
    <Table striped size="sm" className="small">
      <thead>
        <tr>
          <th>Metadata</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>USGS site code</td>
          <td>{data.id.slice(5)}</td>
        </tr>
        <tr>
          <td>Site name</td>
          <td>{data.properties.name}</td>
        </tr>
        <tr>
          <td>Latitude</td>
          <td>{data.geometry?.coordinates?.[1]}</td>
        </tr>
        <tr>
          <td>Longitude</td>
          <td>{data.geometry?.coordinates?.[0]}</td>
        </tr>
        <tr>
          <td>HUC</td>
          <td>{data.properties?.huc12?.slice(6)}</td>
        </tr>
        <tr>
          <td>Drainage (sq. km.)</td>
          <td>{data.properties.drainage_area_km2}</td>
        </tr>
      </tbody>
    </Table>
  );
};
