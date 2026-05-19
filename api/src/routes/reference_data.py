"""
Reference data collection endpoints (configurations, units, variables).

These are lookup/domain tables used to validate and describe timeseries data.
"""

import time
import traceback

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..auth import effective_limit_for_request
from ..database import execute_query, sanitize_string, trino_catalog, trino_schema
from .utils import create_ogc_geojson_response, prepare_for_serialization

router = APIRouter()


@router.get("/collections/configurations/items")
async def get_configuration_items(
    request: Request,
    name: str | None = Query(None, description="Filter by configuration name"),
    timeseries_type: str | None = Query(None, description="Filter by type (primary, secondary)"),
    limit: int | None = Query(
        None, ge=1, description="Maximum number of items to return (omit to return all)"
    ),
    offset: int | None = Query(
        None, ge=0, description="Starting index for pagination"
    ),
):
    """Get configuration definitions.

    Configurations describe data sources (e.g., 'nwm30_retrospective',
    'usgs_observations') with their type (primary or secondary) and description.
    """
    try:
        limit = effective_limit_for_request(request, limit)

        where_conditions = []

        if name:
            safe_name = sanitize_string(name)
            where_conditions.append(f"name = '{safe_name}'")

        if timeseries_type:
            safe_timeseries_type = sanitize_string(timeseries_type)
            where_conditions.append(f"timeseries_type = '{safe_timeseries_type}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        pagination = ""
        if offset is not None:
            pagination += f" OFFSET {offset}"
        if limit is not None:
            pagination += f" LIMIT {limit}"

        query = f"""
            SELECT *
            FROM {trino_catalog}.{trino_schema}.configurations
            WHERE {where_clause}
            ORDER BY name
            {pagination}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Configurations query execution time: {query_time:.3f} seconds")

        if not df.empty:
            df = prepare_for_serialization(df)
        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/configurations",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configurations: {str(e)}",
        ) from e


@router.get("/collections/configurations_summary/items")
async def get_configurations_summary_items(
    request: Request,
    configuration_name: str | None = Query(None, description="Filter by configuration name"),
    timeseries_type: str | None = Query(None, description="Filter by type (primary, secondary)"),
    limit: int | None = Query(
        None, ge=1, description="Maximum number of items to return (omit to return all)"
    ),
    offset: int | None = Query(
        None, ge=0, description="Starting index for pagination"
    ),
):
    """Get configuration summary rows from iceberg.teehr.configurations_summary.

    Returns one row per configuration with aggregate statistics such as
    time ranges, location counts, and associated variable/unit metadata.
    """
    try:
        limit = effective_limit_for_request(request, limit)

        where_conditions = []

        if configuration_name:
            safe_name = sanitize_string(configuration_name)
            where_conditions.append(f"configuration_name = '{safe_name}'")

        if timeseries_type:
            safe_timeseries_type = sanitize_string(timeseries_type)
            where_conditions.append(f"timeseries_type = '{safe_timeseries_type}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        pagination = ""
        if offset is not None:
            pagination += f" OFFSET {offset}"
        if limit is not None:
            pagination += f" LIMIT {limit}"

        query = f"""
            SELECT
                configuration_name,
                variable_name,
                unit_name,
                min_reference_time,
                max_reference_time,
                min_value_time,
                max_value_time,
                n_locations,
                description,
                timeseries_type,
                location_id_prefix,
                created_at,
                updated_at
            FROM {trino_catalog}.{trino_schema}.configurations_summary
            WHERE {where_clause}
            ORDER BY configuration_name
            {pagination}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Configurations summary query execution time: {query_time:.3f} seconds")

        if not df.empty:
            df = prepare_for_serialization(df, datetime_columns=[
                "min_reference_time",
                "max_reference_time",
                "min_value_time",
                "max_value_time",
                "created_at",
                "updated_at",
            ])
        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/configurations_summary",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configurations summary: {str(e)}",
        ) from e


@router.get("/collections/units/items")
async def get_unit_items(
    request: Request,
    name: str | None = Query(None, description="Filter by unit name"),
    limit: int | None = Query(
        None, ge=1, description="Maximum number of items to return (omit to return all)"
    ),
    offset: int | None = Query(
        None, ge=0, description="Starting index for pagination"
    ),
):
    """Get unit definitions.

    Units describe measurement units (e.g., 'm^3/s', 'ft^3/s') with optional
    conversion factors or descriptions.
    """
    try:
        limit = effective_limit_for_request(request, limit)

        where_conditions = []

        if name:
            safe_name = sanitize_string(name)
            where_conditions.append(f"name = '{safe_name}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        pagination = ""
        if offset is not None:
            pagination += f" OFFSET {offset}"
        if limit is not None:
            pagination += f" LIMIT {limit}"

        query = f"""
            SELECT *
            FROM {trino_catalog}.{trino_schema}.units
            WHERE {where_clause}
            ORDER BY name
            {pagination}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Units query execution time: {query_time:.3f} seconds")

        if not df.empty:
            df = prepare_for_serialization(df)
        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/units",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load units: {str(e)}",
        ) from e


@router.get("/collections/variables/items")
async def get_variable_items(
    request: Request,
    name: str | None = Query(None, description="Filter by variable name"),
    limit: int | None = Query(
        None, ge=1, description="Maximum number of items to return (omit to return all)"
    ),
    offset: int | None = Query(
        None, ge=0, description="Starting index for pagination"
    ),
):
    """Get variable definitions.

    Variables describe measured quantities (e.g., 'streamflow_hourly_inst')
    with their descriptions.
    """
    try:
        limit = effective_limit_for_request(request, limit)

        where_conditions = []

        if name:
            safe_name = sanitize_string(name)
            where_conditions.append(f"name = '{safe_name}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        pagination = ""
        if offset is not None:
            pagination += f" OFFSET {offset}"
        if limit is not None:
            pagination += f" LIMIT {limit}"

        query = f"""
            SELECT *
            FROM {trino_catalog}.{trino_schema}.variables
            WHERE {where_clause}
            ORDER BY name
            {pagination}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Variables query execution time: {query_time:.3f} seconds")

        if not df.empty:
            df = prepare_for_serialization(df)
        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/variables",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load variables: {str(e)}",
        ) from e


@router.get("/collections/attributes/items")
async def get_attribute_items(
    request: Request,
    name: str | None = Query(None, description="Filter by attribute name"),
    limit: int | None = Query(
        None, ge=1, description="Maximum number of items to return (omit to return all)"
    ),
    offset: int | None = Query(
        None, ge=0, description="Starting index for pagination"
    ),
):
    """Get attribute definitions.

    Attributes define the available location attribute types (e.g., 'drainage_area_km2',
    'state', 'huc8') with their descriptions.
    """
    try:
        limit = effective_limit_for_request(request, limit)

        where_conditions = []

        if name:
            safe_name = sanitize_string(name)
            where_conditions.append(f"name = '{safe_name}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        pagination = ""
        if offset is not None:
            pagination += f" OFFSET {offset}"
        if limit is not None:
            pagination += f" LIMIT {limit}"

        query = f"""
            SELECT *
            FROM {trino_catalog}.{trino_schema}.attributes
            WHERE {where_clause}
            ORDER BY name
            {pagination}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Attributes query execution time: {query_time:.3f} seconds")

        if not df.empty:
            df = prepare_for_serialization(df)
        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/attributes",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load attributes: {str(e)}",
        ) from e


@router.get("/collections/location_attributes/items")
async def get_location_attribute_items(
    request: Request,
    location_id: list[str] | None = Query(
        None, description="Filter by location ID(s) - can be specified multiple times"
    ),
    prefix: str | None = Query(
        None, description="Filter by location ID prefix (e.g., 'usgs', 'nwm')"
    ),
    attribute_name: list[str] | None = Query(
        None, description="Filter by attribute name(s) - can be specified multiple times"
    ),
    limit: int | None = Query(
        None, ge=1, description="Maximum number of items to return (omit to return all)"
    ),
    offset: int | None = Query(
        None, ge=0, description="Starting index for pagination"
    ),
):
    """Get location attribute values.

    Returns the attribute values associated with locations. Each row is a
    location_id + attribute_name + value triple.

    Use this endpoint to:
    - Get all attributes for a specific location
    - Get all attributes for multiple locations (repeat location_id parameter)
    - Get all attributes for locations with a specific prefix (e.g., 'usgs')
    - Get one or more specific attributes across all locations (repeat attribute_name)
    - Query attribute values without geometry overhead
    """
    try:
        limit = effective_limit_for_request(request, limit)

        where_conditions = []

        if location_id:
            # Multiple location IDs - use IN clause
            safe_locations = [f"'{sanitize_string(loc)}'" for loc in location_id]
            where_conditions.append(f"location_id IN ({', '.join(safe_locations)})")

        if prefix:
            safe_prefix = sanitize_string(prefix)
            where_conditions.append(f"location_id LIKE '{safe_prefix}-%'")

        if attribute_name:
            safe_attrs = [f"'{sanitize_string(a)}'" for a in attribute_name]
            where_conditions.append(f"attribute_name IN ({', '.join(safe_attrs)})")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        pagination = ""
        if offset is not None:
            pagination += f" OFFSET {offset}"
        if limit is not None:
            pagination += f" LIMIT {limit}"

        query = f"""
            SELECT *
            FROM {trino_catalog}.{trino_schema}.location_attributes
            WHERE {where_clause}
            ORDER BY location_id, attribute_name
            {pagination}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Location attributes query execution time: {query_time:.3f} seconds")

        if not df.empty:
            df = prepare_for_serialization(df)
        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/location_attributes",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        # Add pagination links
        if limit is not None and len(items) == limit:
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(str(request.url))
            query_params = parse_qs(parsed.query)
            query_params["offset"] = [str((offset or 0) + limit)]
            query_params["limit"] = [str(limit)]
            next_query = urlencode({k: v[0] for k, v in query_params.items()})
            next_url = urlunparse(parsed._replace(query=next_query))
            response["links"].append(
                {"href": next_url, "rel": "next", "type": "application/json"}
            )

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load location attributes: {str(e)}",
        ) from e


@router.get("/collections/configuration_completeness/items")
async def get_configuration_completeness_items(
    request: Request,
    configuration_name: str | None = Query(None, description="Filter by configuration name"),
    variable_name: str | None = Query(None, description="Filter by variable name"),
    limit: int | None = Query(None, ge=1, description="Maximum number of items to return"),
    offset: int | None = Query(None, ge=0, description="Starting index for pagination"),
):
    """Get primary timeseries completeness aggregation rows.

    Returns rows with: spatial_aggregate, period, actual_count,
    expected_count, completeness, configuration_name, variable_name.
    """
    try:
        limit = effective_limit_for_request(request, limit)

        where_conditions = []
        if configuration_name:
            safe_cfg = sanitize_string(configuration_name)
            where_conditions.append(f"configuration_name = '{safe_cfg}'")
        if variable_name:
            safe_var = sanitize_string(variable_name)
            where_conditions.append(f"variable_name = '{safe_var}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        pagination = ""
        if offset is not None:
            pagination += f" OFFSET {offset}"
        if limit is not None:
            pagination += f" LIMIT {limit}"

        query = f"""
            SELECT
                spatial_aggregate,
                period,
                actual_count,
                expected_count,
                completeness,
                configuration_name,
                variable_name
            FROM {trino_catalog}.{trino_schema}.configuration_completeness
            WHERE {where_clause}
            ORDER BY spatial_aggregate, period
            {pagination}
        """

        query_start = time.time()
        df = execute_query(query)
        print(f"Configuration completeness query: {time.time() - query_start:.3f}s")

        if not df.empty:
            df = prepare_for_serialization(df, datetime_columns=["period"])
        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/configuration_completeness",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        if "TABLE_NOT_FOUND" in str(e) or "does not exist" in str(e).lower():
            empty_response = {
                "items": [],
                "numberReturned": 0,
                "links": [
                    {"href": str(request.url), "rel": "self", "type": "application/json"},
                ],
            }
            return JSONResponse(content=empty_response, media_type="application/json")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configuration_completeness: {str(e)}",
        ) from e


@router.get("/collections/configurations_by_location/items")
async def get_configurations_by_location_items(
    request: Request,
    configuration_name: str | None = Query(None, description="Filter by configuration name"),
    location_id: str | None = Query(None, description="Filter by location ID (alias for primary_location_id)"),
    extra_fields: list[str] | None = Query(None, description="Additional field names to include"),
    limit: int | None = Query(None, ge=1, description="Maximum number of items to return"),
    offset: int | None = Query(None, ge=0, description="Starting index for pagination"),
):
    """Get configurations by location summary rows (tabular, no geometry binary).

    Returns one row per location with associated configuration names, variable
    names, unit names, and time range statistics.
    """
    # Allowlist of all valid optional fields to prevent SQL injection.
    # Keep the client-visible field names stable, but map any mixed-case
    # identifiers to quoted SQL identifiers so Trino preserves their case.
    ALLOWED_EXTRA_FIELD_SQL = {
        'min_reference_time': 'min_reference_time',
        'max_reference_time': 'max_reference_time',
        'num_timeseries': 'num_timeseries',
        'is_active': 'is_active',
        'has_inst_discharge': 'has_inst_discharge',
        'has_inst_stage': 'has_inst_stage',
        'has_mean_daily_discharge': 'has_mean_daily_discharge',
        'has_max_daily_discharge': 'has_max_daily_discharge',
        'has_mean_daily_stage': 'has_mean_daily_stage',
        'has_max_daily_stage': 'has_max_daily_stage',
        'site_type_code': 'site_type_code',
        'state_name': 'state_name',
        'county': 'county',
        'county_name': 'county_name',
        'nws_region': 'nws_region',
        'wfo': 'wfo',
        'rfc': 'rfc',
        'rfc_action_flow_cms': 'rfc_action_flow_cms',
        'rfc_minor_flow_cms': 'rfc_minor_flow_cms',
        'rfc_moderate_flow_cms': 'rfc_moderate_flow_cms',
        'rfc_major_flow_cms': 'rfc_major_flow_cms',
        'nwm30_calb': 'nwm30_calb',
        'disturbance_index': 'disturbance_index',
        'gagesII_class': '"gagesII_class"',
        'huc2': 'huc2',
        'huc4': 'huc4',
        'huc6': 'huc6',
        'huc8': 'huc8',
        'huc10': 'huc10',
        'huc12': 'huc12',
        'drainage_area': 'drainage_area',
        'elev_mean_m': 'elev_mean_m',
        'relief_ratio': 'relief_ratio',
        'stream_order': 'stream_order',
        'sinuousity': 'sinuousity',
        'topo_wetness_index': 'topo_wetness_index',
        'runoff_ratio': 'runoff_ratio',
        'runoff_mean_mm': 'runoff_mean_mm',
        'bfi_mean': 'bfi_mean',
        'horton_percent': 'horton_percent',
        'pcpn_mean_mm': 'pcpn_mean_mm',
        'pcpn_percent_snow': 'pcpn_percent_snow',
        'temp_mean_c': 'temp_mean_c',
        'q10_cms': 'q10_cms',
        'q50_cms': 'q50_cms',
        'q90_cms': 'q90_cms',
        'max_record': 'max_record',
        'first_year': 'first_year',
        'last_year': 'last_year',
        'season_index': 'season_index',
        'percent_imperv': 'percent_imperv',
        'percent_irrig': 'percent_irrig',
        'percent_developed': 'percent_developed',
        'percent_canals': 'percent_canals',
        'ndams': 'ndams',
        'ndams_major': 'ndams_major',
        'ndams_major_100km2': 'ndams_major_100km2',
        'ndams_100km2': 'ndams_100km2',
        'dam_dist_nearest_km': 'dam_dist_nearest_km',
        'storage_max_Mlkm2': '"storage_max_Mlkm2"',
        'storage_normal_Mlkm2': '"storage_normal_Mlkm2"',
        'withdrawals_Mlkm2': '"withdrawals_Mlkm2"',
        'aggecoregion': 'aggecoregion',
        'ecoregion_L2': '"ecoregion_L2"',
        'epa_ecoregion_l1': 'epa_ecoregion_l1',
        'epa_ecoregion_l2': 'epa_ecoregion_l2',
        'iana_timezone': 'iana_timezone',
        'timezone': 'timezone',
    }
    ALLOWED_EXTRA_FIELDS = set(ALLOWED_EXTRA_FIELD_SQL)

    try:
        limit = effective_limit_for_request(request, limit)

        where_conditions = []
        if configuration_name:
            safe_name = sanitize_string(configuration_name)
            where_conditions.append(f"configuration_name = '{safe_name}'")

        if location_id:
            safe_id = sanitize_string(location_id)
            where_conditions.append(f"primary_location_id = '{safe_id}'")

        where_clause = ("WHERE " + " AND ".join(where_conditions)) if where_conditions else ""

        pagination = ""
        if offset is not None:
            pagination += f" OFFSET {offset}"
        if limit is not None:
            pagination += f" LIMIT {limit}"

        # Base fields always returned
        base_fields = [
            "primary_location_id", "configuration_name", "variable_name",
            "unit_name", "min_reference_time", "max_reference_time",
            "min_value_time", "max_value_time", "num_members",
        ]

        # Validated extra fields requested by the client
        safe_extras = [f for f in (extra_fields or []) if f in ALLOWED_EXTRA_FIELDS]
        # Deduplicate while preserving order
        all_fields = list(dict.fromkeys(base_fields + safe_extras))
        select_clause = ",\n                ".join(all_fields)

        query = f"""
            SELECT
                {select_clause}
            FROM {trino_catalog}.{trino_schema}.configurations_by_location
            {where_clause}
            ORDER BY primary_location_id
            {pagination}
        """

        print(f"[DEBUG] Configurations by location query: {query}")
        query_start = time.time()
        df = execute_query(query)
        print(f"Configurations by location items query: {time.time() - query_start:.3f}s")

        datetime_cols = [f for f in ["min_reference_time", "max_reference_time",
                                      "min_value_time", "max_value_time"] if f in df.columns]
        if not df.empty:
            df = prepare_for_serialization(df, datetime_columns=datetime_cols)
        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/configurations_by_location",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[ERROR] Failed to load configurations_by_location:")
        print(f"Error message: {error_msg}")
        print(f"Traceback:\n{tb}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configurations_by_location: {error_msg}",
        ) from e


@router.get("/collections/configurations_by_location/expanded")
async def get_configurations_by_location_expanded(
    request: Request,
    location_id: str | None = Query(None, description="Filter by location ID"),
):
    """Get configurations expanded into individual rows (one per config/variable/unit combo).

    Queries the base row for the given location from configurations_by_location,
    then expands the configuration_names, variable_names, and unit_names arrays
    into individual rows in Python.
    """
    if not location_id:
        raise HTTPException(status_code=400, detail="location_id parameter is required")

    try:
        safe_id = sanitize_string(location_id)

        # Each row is already one configuration/variable/unit — no expansion needed
        query = f"""
            SELECT
                primary_location_id,
                configuration_name,
                variable_name,
                unit_name,
                min_reference_time,
                max_reference_time,
                min_value_time,
                max_value_time,
                num_members
            FROM {trino_catalog}.{trino_schema}.configurations_by_location
            WHERE primary_location_id = '{safe_id}'
            ORDER BY configuration_name, variable_name, unit_name
        """

        print(f"[DEBUG] Expanded configurations query: {query}")
        query_start = time.time()
        df = execute_query(query)
        print(f"Configurations by location expanded query: {time.time() - query_start:.3f}s")

        datetime_cols = [c for c in ["min_reference_time", "max_reference_time",
                                     "min_value_time", "max_value_time"] if c in df.columns]
        if not df.empty:
            df = prepare_for_serialization(df, datetime_columns=datetime_cols)
            df = df.rename(columns={"primary_location_id": "location_id"})

        items = df.to_dict(orient="records") if not df.empty else []
        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/configurations_by_location",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[ERROR] Failed to load expanded configurations:")
        print(f"Error message: {error_msg}")
        print(f"Traceback:\n{tb}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load expanded configurations: {error_msg}",
        ) from e


@router.get("/collections/configurations_by_location/location-ids")
async def get_configurations_by_location_ids(
    configuration_name: str = Query(..., description="Filter by configuration name"),
    variable_name: str | None = Query(None, description="Filter by variable name"),
):
    """Return a distinct list of primary_location_id values for the given configuration and variable."""
    try:
        safe_name = sanitize_string(configuration_name)
        where_conditions = [f"configuration_name = '{safe_name}'"]
        if variable_name:
            safe_var = sanitize_string(variable_name)
            where_conditions.append(f"variable_name = '{safe_var}'")
        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT DISTINCT primary_location_id
            FROM {trino_catalog}.{trino_schema}.configurations_by_location
            WHERE {where_clause}
            ORDER BY primary_location_id
        """

        query_start = time.time()
        df = execute_query(query)
        print(f"Configurations by location IDs query: {time.time() - query_start:.3f}s, {len(df)} rows")

        return JSONResponse(content={"location_ids": df["primary_location_id"].tolist()})

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[ERROR] Failed to load configuration location IDs:")
        print(f"Error message: {error_msg}")
        print(f"Traceback:\n{tb}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configuration location IDs: {error_msg}",
        ) from e


@router.get("/collections/configurations_by_location/locations-geojson")
async def get_configurations_by_location_locations_geojson(
    configuration_name: str = Query(..., description="Filter by configuration name"),
    variable_name: str | None = Query(None, description="Filter by variable name"),
):
    """Return a GeoJSON FeatureCollection of locations for a given configuration + variable.

    Joins configurations_by_location with the locations table to obtain geometry,
    so all matching locations are returned regardless of count (no URL-length limits).
    """
    try:
        safe_name = sanitize_string(configuration_name)
        where_conditions = [f"cbl.configuration_name = '{safe_name}'"]
        if variable_name:
            safe_var = sanitize_string(variable_name)
            where_conditions.append(f"cbl.variable_name = '{safe_var}'")
        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT
                l.id AS primary_location_id,
                l.name,
                round(ST_X(ST_GeomFromBinary(l.geometry)), 8) AS lon,
                round(ST_Y(ST_GeomFromBinary(l.geometry)), 8) AS lat
            FROM {trino_catalog}.{trino_schema}.locations l
            WHERE l.geometry IS NOT NULL
              AND l.id IN (
                  SELECT DISTINCT cbl.primary_location_id
                  FROM {trino_catalog}.{trino_schema}.configurations_by_location cbl
                  WHERE {where_clause}
              )
            ORDER BY l.id
        """

        query_start = time.time()
        df = execute_query(query)
        print(f"Configuration locations-geojson query: {time.time() - query_start:.3f}s, {len(df)} rows")

        features = []
        for row in df.itertuples(index=False):
            if row.lon is None or row.lat is None:
                continue
            features.append({
                "type": "Feature",
                "id": row.primary_location_id,
                "geometry": {"type": "Point", "coordinates": [row.lon, row.lat]},
                "properties": {
                    "primary_location_id": row.primary_location_id,
                    "name": row.name,
                },
            })

        return JSONResponse(
            content={"type": "FeatureCollection", "features": features},
            headers={
                "Content-Type": "application/geo+json",
                "Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>",
            },
        )

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[ERROR] Failed to load configuration locations geojson:")
        print(f"Error message: {error_msg}")
        print(f"Traceback:\n{tb}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configuration locations geojson: {error_msg}",
        ) from e


@router.get("/collections/configurations_by_location/geojson")
async def get_configurations_by_location_geojson(
    configuration_name: str | None = Query(None, description="Filter by configuration name"),
    variable_name: str | None = Query(None, description="Filter by variable name"),
    primary_location_id: str | None = Query(None, description="Filter by primary location ID"),
):
    """Get configurations by location as a GeoJSON FeatureCollection.

    Each feature is a Point representing a location, with properties including
    the configuration names, variable names, and unit names associated with it.

    Uses Trino spatial functions to extract lon/lat directly, avoiding the
    geopandas WKB-decoding pass in Python which is slow for large result sets.
    """
    try:
        where_conditions = ["geometry IS NOT NULL"]
        if configuration_name:
            safe_name = sanitize_string(configuration_name)
            where_conditions.append(f"configuration_name = '{safe_name}'")
        if variable_name:
            safe_var = sanitize_string(variable_name)
            where_conditions.append(f"variable_name = '{safe_var}'")
        if primary_location_id:
            safe_id = sanitize_string(primary_location_id)
            where_conditions.append(f"primary_location_id = '{safe_id}'")

        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT
                primary_location_id,
                configuration_name,
                variable_name,
                unit_name,
                round(ST_X(ST_GeomFromBinary(geometry)), 8) AS lon,
                round(ST_Y(ST_GeomFromBinary(geometry)), 8) AS lat
            FROM {trino_catalog}.{trino_schema}.configurations_by_location
            WHERE {where_clause}
            ORDER BY primary_location_id
        """

        query_start = time.time()
        df = execute_query(query)
        print(f"Configurations by location geojson query: {time.time() - query_start:.3f}s")

        # Build GeoJSON directly from lon/lat columns — no geopandas needed
        features = []
        for row in df.itertuples(index=False):
            lon = row.lon
            lat = row.lat
            if lon is None or lat is None:
                continue
            features.append({
                "type": "Feature",
                "id": row.primary_location_id,
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "primary_location_id": row.primary_location_id,
                    "configuration_name": row.configuration_name,
                    "variable_name": row.variable_name,
                    "unit_name": row.unit_name,
                },
            })

        print(f"Configurations by location geojson total: {time.time() - query_start:.3f}s ({len(features)} features)")

        return JSONResponse(
            content={"type": "FeatureCollection", "features": features},
            media_type="application/json",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configurations_by_location geojson: {str(e)}",
        ) from e


@router.get("/collections/configuration_completeness/geometries")
async def get_completeness_geometries(
    request: Request,
    configuration_name: str | None = Query(None, description="Filter by configuration name"),
    variable_name: str | None = Query(None, description="Filter by variable name"),
):
    """Get distinct spatial aggregate geometries from the completeness_summary table.

    Returns a GeoJSON FeatureCollection where each feature represents a unique
    spatial aggregate polygon. Feature properties include 'id' set to the
    spatial_aggregate value so the heatmap hover highlight filter works.
    """
    try:
        where_conditions = []
        if configuration_name:
            safe_cfg = sanitize_string(configuration_name)
            where_conditions.append(f"configuration_name = '{safe_cfg}'")
        if variable_name:
            safe_var = sanitize_string(variable_name)
            where_conditions.append(f"variable_name = '{safe_var}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f"""
            SELECT DISTINCT
                spatial_aggregate AS id,
                geometry
            FROM {trino_catalog}.{trino_schema}.configuration_completeness
            WHERE {where_clause}
            AND geometry IS NOT NULL
            ORDER BY spatial_aggregate
        """

        df = execute_query(query)
        return create_ogc_geojson_response(df, str(request.url))

    except Exception as e:
        if "TABLE_NOT_FOUND" in str(e) or "does not exist" in str(e).lower():
            empty_fc = {"type": "FeatureCollection", "features": [], "numberMatched": 0, "numberReturned": 0}
            return JSONResponse(content=empty_fc, media_type="application/json")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load completeness geometries: {str(e)}",
        ) from e

