"""
Timeseries endpoints (OGC API - Coverages).
"""

import time
from datetime import datetime

import geopandas as gpd
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..database import execute_query, sanitize_string, trino_catalog, trino_schema
from .utils import create_coveragejson_timeseries, parse_subset_parameter

router = APIRouter()


@router.get("/collections/primary_timeseries/coverage")
async def get_primary_timeseries_coverage(
    subset: list[str] = Query(
        [],
        description='OGC subset parameters (e.g., location("id"), time("start:end"))',  # noqa: E501
    ),
    location_id: str | None = Query(
        None, description="Location ID"
    ),
    datetime_param: str | None = Query(
        None,
        alias="datetime",
        description="ISO 8601 datetime interval (e.g., 2020-01-01/2020-12-31)",
    ),
    parameter: str | None = Query(
        None, description="Parameter name (alternative to subset)"
    ),
    configuration: str | None = Query(
        None, description="Configuration name (alternative to subset)"
    ),
    f: str | None = Query(
        "covjson", description="Response format: covjson (default), json"
    ),
):
    """Get primary timeseries coverage (OGC API - Coverages compliant).

    Supports both OGC subset syntax and simple parameters:

    OGC subset examples:
    - subset=location("usgs-01347000")
    - subset=time("2020-01-01T00:00:00Z":"2020-12-31T23:59:59Z")

    Simple parameter examples:
    - location_id=usgs-01347000&datetime=2020-01-01/2020-12-31
    - location_id=usgs-01347000&parameter=streamflow_hourly_inst
    """
    try:
        # Build subset list for non-temporal parameters
        subset_list = list(subset)

        if location_id:
            subset_list.append(f'location("{location_id}")')
        if parameter:
            subset_list.append(f'parameter("{parameter}")')
        if configuration:
            subset_list.append(f'configuration("{configuration}")')

        # Parse subset parameters (non-temporal)
        subsets = parse_subset_parameter(subset_list)

        # Extract location (required)
        if "location" not in subsets:
            raise HTTPException(status_code=400, detail="location_id is required")

        location_id = subsets["location"][0]
        safe_location_id = sanitize_string(location_id)
        where_conditions = [f"location_id = '{safe_location_id}'"]

        # Parse datetime as ISO 8601 interval (standard OGC format)
        if datetime_param:
            if "/" in datetime_param:
                start_str, end_str = datetime_param.split("/", 1)
            else:
                start_str = end_str = datetime_param

            if start_str and start_str != "..":
                start_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                where_conditions.append(
                    f"value_time >= TIMESTAMP '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'"  # noqa: E501
                )
            if end_str and end_str != "..":
                end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                where_conditions.append(
                    f"value_time <= TIMESTAMP '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'"  # noqa: E501
                )

        # Extract parameter
        if "parameter" in subsets:
            parameter_name = subsets["parameter"][0]
            safe_variable = sanitize_string(parameter_name)
            where_conditions.append(f"variable_name = '{safe_variable}'")

        # Extract configuration (optional)
        if "configuration" in subsets:
            configuration = subsets["configuration"][0]
            safe_configuration = sanitize_string(configuration)
            where_conditions.append(f"configuration_name = '{safe_configuration}'")

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT
            'primary' as series_type,
            location_id as primary_location_id,
            reference_time,
            configuration_name,
            variable_name,
            unit_name,
            value_time,
            value
        FROM {trino_catalog}.{trino_schema}.primary_timeseries
        WHERE {where_clause}
        ORDER BY value_time
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")

        if df.empty:
            return JSONResponse(
                content={
                    "type": "Coverage",
                    "domain": {"type": "Domain", "axes": {"t": {"values": []}}},
                    "parameters": {},
                    "ranges": {},
                },
                media_type="application/prs.coverage+json",
            )

        print(f"Query returned {len(df)} primary timeseries records")

        format_start = time.time()
        df["value_time"] = pd.to_datetime(df["value_time"]).dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        if "reference_time" in df.columns:
            mask = pd.notna(df["reference_time"])
            if mask.any():
                df.loc[mask, "reference_time"] = df.loc[
                    mask, "reference_time"
                ].dt.strftime("%Y-%m-%d %H:%M:%S")
            df["reference_time"] = df["reference_time"].fillna("null")
        else:
            df["reference_time"] = "null"

        grouped = df.groupby(
            [
                "series_type",
                "primary_location_id",
                "reference_time",
                "configuration_name",
                "variable_name",
                "unit_name",
            ]
        )

        data = []
        for (
            series_type,
            primary_location_id,
            reference_time,
            configuration_name,
            variable_name,
            unit_name,
        ), group in grouped:
            timeseries_data = {
                "series_type": series_type,
                "primary_location_id": primary_location_id,
                "reference_time": reference_time,
                "configuration_name": configuration_name,
                "variable_name": variable_name,
                "unit_name": unit_name,
                "timeseries": group[["value_time", "value"]].to_dict(orient="records"),
            }
            data.append(timeseries_data)

        format_time = time.time() - format_start
        print(f"Primary formatting time: {format_time:.3f} seconds")

        # Always return CoverageJSON for Coverages endpoint
        loc_coords = None
        if not df.empty and "geometry" in df.columns:
            try:
                geom_series = gpd.GeoSeries.from_wkb(
                    df["geometry"].iloc[0:1].apply(bytes)
                )
                if len(geom_series) > 0:
                    point = geom_series.iloc[0]
                    loc_coords = (point.x, point.y)
            except Exception:
                pass

        coverage = create_coveragejson_timeseries(data, location_id, loc_coords)
        return JSONResponse(
            content=coverage, media_type="application/prs.coverage+json"
        )

    except Exception as e:
        print(f"Primary timeseries error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to load coverage: {str(e)}"
        ) from e


@router.get("/collections/secondary_timeseries/coverage")
async def get_secondary_timeseries_coverage(
    subset: list[str] = Query(
        [],
        description='OGC subset parameters (e.g., location("id"), time("start:end"))',  # noqa: E501
    ),
    location_id: str | None = Query(
        None, description="Location ID"
    ),
    datetime_param: str | None = Query(
        None,
        alias="datetime",
        description="ISO 8601 datetime interval (e.g., 2020-01-01/2020-12-31)",
    ),
    reference_time: str | None = Query(
        None,
        description="ISO 8601 reference time interval (e.g., 2020-01-01/2020-12-31)",  # noqa: E501
    ),
    parameter: str | None = Query(
        None, description="Parameter name (alternative to subset)"
    ),
    configuration: str | None = Query(
        None, description="Configuration name (alternative to subset)"
    ),
    f: str | None = Query(
        "covjson", description="Response format: covjson (default), json"
    ),
):
    """Get secondary timeseries coverage (OGC API - Coverages compliant).

    Supports both OGC subset syntax and simple parameters:
    - datetime: ISO 8601 interval for value_time (e.g., 2020-01-01/2020-12-31)
    - reference_time: ISO 8601 interval for
        reference_time (e.g., 2020-01-01/2020-12-31)
    """
    try:
        # Build subset list for non-temporal parameters
        subset_list = list(subset)

        if location_id:
            subset_list.append(f'location("{location_id}")')
        if parameter:
            subset_list.append(f'parameter("{parameter}")')
        if configuration:
            subset_list.append(f'configuration("{configuration}")')

        # Parse subset parameters (non-temporal)
        subsets = parse_subset_parameter(subset_list)

        # Extract location (required)
        if "location" not in subsets:
            raise HTTPException(status_code=400, detail="location_id is required")

        location_id = subsets["location"][0]
        safe_location_id = sanitize_string(location_id)
        where_conditions = [f"lc.primary_location_id = '{safe_location_id}'"]

        # Parse datetime as ISO 8601 interval (standard OGC format)
        if datetime_param:
            if "/" in datetime_param:
                start_str, end_str = datetime_param.split("/", 1)
            else:
                start_str = end_str = datetime_param

            if start_str and start_str != "..":
                start_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                where_conditions.append(
                    f"st.value_time >= TIMESTAMP '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'"  # noqa: E501
                )
            if end_str and end_str != "..":
                end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                where_conditions.append(
                    f"st.value_time <= TIMESTAMP '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'"  # noqa: E501
                )

        # Parse reference_time as ISO 8601 interval (standard OGC format)
        if reference_time:
            if "/" in reference_time:
                ref_start_str, ref_end_str = reference_time.split("/", 1)
            else:
                ref_start_str = ref_end_str = reference_time

            if ref_start_str and ref_start_str != "..":
                ref_start = datetime.fromisoformat(ref_start_str.replace("Z", "+00:00"))
                where_conditions.append(
                    f"st.reference_time >= TIMESTAMP '{ref_start.strftime('%Y-%m-%d %H:%M:%S')}'"  # noqa: E501
                )
            if ref_end_str and ref_end_str != "..":
                ref_end = datetime.fromisoformat(ref_end_str.replace("Z", "+00:00"))
                where_conditions.append(
                    f"st.reference_time <= TIMESTAMP '{ref_end.strftime('%Y-%m-%d %H:%M:%S')}'"  # noqa: E501
                )

        # Extract parameter
        if "parameter" in subsets:
            parameter_name = subsets["parameter"][0]
            where_conditions.append(
                f"st.variable_name = '{sanitize_string(parameter_name)}'"
            )

        # Extract configuration
        if "configuration" in subsets:
            configuration = subsets["configuration"][0]
            where_conditions.append(
                f"st.configuration_name = '{sanitize_string(configuration)}'"
            )

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT
            st.value_time, st.value, st.configuration_name, st.variable_name,
            st.unit_name, st.member, st.reference_time,
            lc.primary_location_id, 'secondary' as series_type
        FROM {trino_catalog}.{trino_schema}.secondary_timeseries st
        JOIN {trino_catalog}.{trino_schema}.location_crosswalks lc
        ON st.location_id = lc.secondary_location_id
        WHERE {where_clause}
        ORDER BY st.value_time
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Secondary query execution time: {query_time:.3f} seconds")

        if df.empty:
            return JSONResponse(
                content={
                    "type": "Coverage",
                    "domain": {"type": "Domain", "axes": {"t": {"values": []}}},
                    "parameters": {},
                    "ranges": {},
                },
                media_type="application/prs.coverage+json",
            )

        print(f"Query returned {len(df)} secondary timeseries records")

        format_start = time.time()
        df["value_time"] = pd.to_datetime(df["value_time"]).dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        if "reference_time" in df.columns:
            mask = pd.notna(df["reference_time"])
            if mask.any():
                df.loc[mask, "reference_time"] = df.loc[
                    mask, "reference_time"
                ].dt.strftime("%Y-%m-%d %H:%M:%S")
            df["reference_time"] = df["reference_time"].fillna("null")
        else:
            df["reference_time"] = "null"

        df["member"] = df["member"].fillna("null")

        grouped = df.groupby(
            [
                "series_type",
                "primary_location_id",
                "reference_time",
                "configuration_name",
                "variable_name",
                "unit_name",
                "member",
            ]
        )

        data = []
        for (
            series_type,
            primary_location_id,
            reference_time,
            configuration_name,
            variable_name,
            unit_name,
            member,
        ), group in grouped:
            timeseries_data = {
                "series_type": series_type,
                "primary_location_id": primary_location_id,
                "reference_time": reference_time if reference_time != "null" else None,  # noqa: E501
                "configuration_name": configuration_name,
                "variable_name": variable_name,
                "unit_name": unit_name,
                "member": member if member != "null" else None,
                "timeseries": group[["value_time", "value"]].to_dict(orient="records"),  # noqa: E501
            }
            data.append(timeseries_data)

        format_time = time.time() - format_start
        print(f"Secondary formatting time: {format_time:.3f} seconds")

        # Always return CoverageJSON for Coverages endpoint
        coverage = create_coveragejson_timeseries(data, location_id, None)
        return JSONResponse(
            content=coverage, media_type="application/prs.coverage+json"
        )

    except Exception as e:
        print(f"Secondary timeseries error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to load coverage: {str(e)}"
        ) from e
