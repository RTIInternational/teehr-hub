"""
OGC API foundation endpoints (landing page, conformance, collections).
"""

from fastapi import APIRouter, HTTPException

from ..database import execute_query, trino_catalog, trino_schema
from ..models import (
    Collection,
    CollectionsResponse,
    ConformanceResponse,
    Extent,
    LandingPage,
    Link,
)

router = APIRouter()

# OGC link relation for queryables
REL_QUERYABLES = "http://www.opengis.net/def/rel/ogc/1.0/queryables"
CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"


@router.get("/", response_model=LandingPage)
async def root():
    """OGC API Landing page with links to all resources."""
    return LandingPage(
        title="TEEHR Dashboard API",
        description="OGC-compliant API for hydrological timeseries and metrics data",
        links=[
            Link(href="/", rel="self", type="application/json", title="This document"),
            Link(
                href="/api",
                rel="service-desc",
                type="application/vnd.oai.openapi+json;version=3.0",
                title="API definition",
            ),
            Link(
                href="/docs",
                rel="service-doc",
                type="text/html",
                title="API documentation",
            ),
            Link(
                href="/conformance",
                rel="conformance",
                type="application/json",
                title="OGC API conformance classes",
            ),
            Link(
                href="/collections",
                rel="data",
                type="application/json",
                title="Collections",
            ),
        ],
    )


@router.get("/conformance", response_model=ConformanceResponse)
async def conformance():
    """OGC API conformance declaration."""
    return ConformanceResponse(
        conformsTo=[
            # OGC API - Common
            "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
            "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page",
            "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json",
            # OGC API - Features
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
            "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables",
            # OGC API - Coverages
            "http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/core",
            "http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-subset",
            # OGC API - EDR
            "http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core",
        ]
    )


@router.get("/collections", response_model=CollectionsResponse)
async def get_collections():
    """List all available data collections."""

    # Get extent information from database
    try:
        # Get spatial extent from locations
        # Note: geometry is stored as WKB (varbinary), need to convert
        spatial_query = f"""
        SELECT
            MIN(ST_X(ST_GeomFromBinary(geometry))) as min_lon,
            MAX(ST_X(ST_GeomFromBinary(geometry))) as max_lon,
            MIN(ST_Y(ST_GeomFromBinary(geometry))) as min_lat,
            MAX(ST_Y(ST_GeomFromBinary(geometry))) as max_lat
        FROM {trino_catalog}.{trino_schema}.locations
        WHERE id LIKE 'usgs-%'
        """

        # Get temporal extent from timeseries
        temporal_query = f"""
        SELECT
            MIN(value_time) as min_time,
            MAX(value_time) as max_time
        FROM (
            SELECT value_time
            FROM {trino_catalog}.{trino_schema}.primary_timeseries
            UNION ALL
            SELECT value_time
            FROM {trino_catalog}.{trino_schema}.secondary_timeseries
        )
        """

        spatial_df = execute_query(spatial_query, max_rows=1)
        temporal_df = execute_query(temporal_query, max_rows=1)

        # Build extent
        spatial_extent = {
            "bbox": [
                [
                    float(spatial_df["min_lon"].iloc[0]),
                    float(spatial_df["min_lat"].iloc[0]),
                    float(spatial_df["max_lon"].iloc[0]),
                    float(spatial_df["max_lat"].iloc[0]),
                ]
            ],
            "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
        }

        temporal_extent = {
            "interval": [
                [
                    temporal_df["min_time"].iloc[0].isoformat() + "Z",
                    temporal_df["max_time"].iloc[0].isoformat() + "Z",
                ]
            ],
            "trs": "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian",
        }

    except Exception as e:
        print(f"Warning: Could not calculate extents: {e}")
        spatial_extent = None
        temporal_extent = None

    collections = [
        Collection(
            id="locations",
            title="Observation Locations",
            description="Geographic locations where observations are collected",
            links=[
                Link(
                    href="/collections/locations", rel="self", type="application/json"
                ),
                Link(
                    href="/collections/locations/items",
                    rel="items",
                    type="application/geo+json",
                ),
                Link(
                    href="/collections/locations/queryables",
                    rel=REL_QUERYABLES,
                    type="application/schema+json",
                ),
            ],
            extent=Extent(spatial=spatial_extent) if spatial_extent else None,
            itemType="feature",
            crs=[CRS84],
        ),
        Collection(
            id="primary_timeseries",
            title="Primary Timeseries",
            description="Observed timeseries data at monitoring locations",
            links=[
                Link(
                    href="/collections/primary_timeseries",
                    rel="self",
                    type="application/json",
                ),
                Link(
                    href="/collections/primary_timeseries/coverage",
                    rel="coverage",
                    type="application/prs.coverage+json",
                ),
                Link(
                    href="/collections/primary_timeseries/queryables",
                    rel=REL_QUERYABLES,
                    type="application/schema+json",
                ),
            ],
            extent=Extent(spatial=spatial_extent, temporal=temporal_extent)
            if spatial_extent and temporal_extent
            else None,
            crs=[CRS84],
        ),
        Collection(
            id="secondary_timeseries",
            title="Secondary Timeseries",
            description="Forecast/simulated timeseries data",
            links=[
                Link(
                    href="/collections/secondary_timeseries",
                    rel="self",
                    type="application/json",
                ),
                Link(
                    href="/collections/secondary_timeseries/coverage",
                    rel="coverage",
                    type="application/prs.coverage+json",
                ),
                Link(
                    href="/collections/secondary_timeseries/queryables",
                    rel=REL_QUERYABLES,
                    type="application/schema+json",
                ),
            ],
            extent=Extent(spatial=spatial_extent, temporal=temporal_extent)
            if spatial_extent and temporal_extent
            else None,
            crs=[CRS84],
        ),
        Collection(
            id="sim_metrics_by_location",
            title="Simulation Metrics by Location",
            description="Performance metrics for simulations by location",
            links=[
                Link(
                    href="/collections/sim_metrics_by_location",
                    rel="self",
                    type="application/json",
                ),
                Link(
                    href="/collections/sim_metrics_by_location/items",
                    rel="items",
                    type="application/geo+json",
                ),
                Link(
                    href="/collections/sim_metrics_by_location/queryables",
                    rel=REL_QUERYABLES,
                    type="application/schema+json",
                ),
            ],
            extent=Extent(spatial=spatial_extent) if spatial_extent else None,
            itemType="feature",
            crs=[CRS84],
        ),
        Collection(
            id="fcst_metrics_by_location",
            title="Forecast Metrics by Location",
            description="Performance metrics for forecasts by location",
            links=[
                Link(
                    href="/collections/fcst_metrics_by_location",
                    rel="self",
                    type="application/json",
                ),
                Link(
                    href="/collections/fcst_metrics_by_location/items",
                    rel="items",
                    type="application/geo+json",
                ),
                Link(
                    href="/collections/fcst_metrics_by_location/queryables",
                    rel=REL_QUERYABLES,
                    type="application/schema+json",
                ),
            ],
            extent=Extent(spatial=spatial_extent) if spatial_extent else None,
            itemType="feature",
            crs=[CRS84],
        ),
        Collection(
            id="fcst_metrics_by_lead_time_bins",
            title="Forecast Metrics by Lead Time",
            description="Performance metrics for forecasts by lead time bins",
            links=[
                Link(
                    href="/collections/fcst_metrics_by_lead_time_bins",
                    rel="self",
                    type="application/json",
                ),
                Link(
                    href="/collections/fcst_metrics_by_lead_time_bins/items",
                    rel="items",
                    type="application/geo+json",
                ),
                Link(
                    href="/collections/fcst_metrics_by_lead_time_bins/queryables",
                    rel=REL_QUERYABLES,
                    type="application/schema+json",
                ),
            ],
            extent=Extent(spatial=spatial_extent) if spatial_extent else None,
            itemType="feature",
            crs=[CRS84],
        ),
    ]

    return CollectionsResponse(
        links=[
            Link(href="/collections", rel="self", type="application/json"),
            Link(href="/", rel="root", type="application/json"),
        ],
        collections=collections,
    )


@router.get("/collections/{collection_id}", response_model=Collection)
async def get_collection(collection_id: str):
    """Get metadata for a specific collection."""

    # Get the collections list
    collections_response = await get_collections()

    # Find the requested collection
    for collection in collections_response.collections:
        if collection.id == collection_id:
            return collection

    raise HTTPException(
        status_code=404, detail=f"Collection '{collection_id}' not found"
    )
