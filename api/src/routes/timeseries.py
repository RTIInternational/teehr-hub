"""
Timeseries endpoints (OGC API - Coverages).
"""

import time
from datetime import datetime

import geopandas as gpd
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..database import execute_query, sanitize_string, trino_catalog, trino_schema
from .utils import create_ogc_geojson_response

router = APIRouter()


@router.get("/collections/primary_timeseries/items")
async def get_primary_timeseries_items(
    request: Request,
    location_id: str = Query(
        ..., description="Location ID"
    ),
    datetime_param: str | None = Query(
        None,
        alias="datetime",
        description="ISO 8601 datetime interval (e.g., 2020-01-01/2020-12-31)",
    ),
    parameter: str | None = Query(None, description="Variable name filter"),
    configuration: str | None = Query(None, description="Configuration name filter"),
    f: str | None = Query("json", description="Output format: json or geojson"),
):
    """Get primary timeseries (observations) for a location.

    Returns array of timeseries objects with streamflow data.
    """
    try:
        print(f"Primary timeseries called with: location_id={location_id}, datetime={datetime_param}, parameter={parameter}, configuration={configuration}")
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
        # Filter by variable/parameter
        if parameter:
            safe_parameter = sanitize_string(parameter)
            where_conditions.append(f"variable_name = '{safe_parameter}'")

        # Filter by configuration
        if configuration:
            safe_configuration = sanitize_string(configuration)
            where_conditions.append(f"configuration_name = '{safe_configuration}'")
        where_clause = " AND ".join(where_conditions)

        # Build query based on format
        if f and f.lower() == "geojson":
            query = f"""
            SELECT
                pt.location_id as primary_location_id,
                pt.reference_time,
                pt.configuration_name,
                pt.variable_name,
                pt.unit_name,
                pt.value_time,
                pt.value,
                l.geometry
            FROM {trino_catalog}.{trino_schema}.primary_timeseries pt
            JOIN {trino_catalog}.{trino_schema}.locations l ON pt.location_id = l.id
            WHERE {where_clause}
            ORDER BY pt.value_time
            """
        else:
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
            return JSONResponse(content=[], media_type="application/json")

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

        if f and f.lower() == "geojson":
            geojson = create_ogc_geojson_response(
                df,
                str(request.url),
                collection_id="secondary_timeseries",
            )

            return JSONResponse(
                content=geojson,
                headers={
                    "Content-Type": "application/geo+json",
                    "Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>",  # noqa: E501
                },
            )

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

        return JSONResponse(content=data, media_type="application/json")

    except Exception as e:
        print(f"Primary timeseries error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to load coverage: {str(e)}"
        ) from e


@router.get("/collections/secondary_timeseries/items")
async def get_secondary_timeseries_items(
    request: Request,
    location_id: str = Query(..., description="Location ID"),
    datetime_param: str | None = Query(
        None,
        alias="datetime",
        description="ISO 8601 datetime interval (e.g., 2020-01-01/2020-12-31)",
    ),
    reference_time: str | None = Query(
        None,
        description="ISO 8601 reference time interval (e.g., 2020-01-01/2020-12-31)",  # noqa: E501
    ),
    parameter: str | None = Query(None, description="Variable name filter"),
    configuration: str | None = Query(None, description="Configuration name filter"),
    f: str | None = Query("json", description="Output format: json or geojson"),
):
    """Get secondary timeseries (model outputs/forecasts) for a location.

    Supports filtering by:
    - datetime: ISO 8601 interval for value_time (e.g., 2020-01-01/2020-12-31)
    - reference_time: ISO 8601 interval for reference_time (e.g., 2025-11-01/..)
    - parameter: Variable name (e.g., streamflow_hourly_inst)
    - configuration: Configuration name (e.g., nwm30_medium_range)

    Returns array of timeseries objects, one per unique combination of
    reference_time, configuration, variable, and member.
    """
    try:
        print(f"Secondary timeseries called with: location_id={location_id}, datetime={datetime_param}, reference_time={reference_time}, parameter={parameter}, configuration={configuration}")
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
        # Filter by variable/parameter
        if parameter:
            safe_parameter = sanitize_string(parameter)
            where_conditions.append(f"st.variable_name = '{safe_parameter}'")

        # Filter by configuration
        if configuration:
            safe_configuration = sanitize_string(configuration)
            where_conditions.append(f"st.configuration_name = '{safe_configuration}'")
        where_clause = " AND ".join(where_conditions)

        # Build query based on format
        if f and f.lower() == "geojson":
            query = f"""
            SELECT
                st.value_time, st.value, st.configuration_name, st.variable_name,
                st.unit_name, st.member, st.reference_time,
                lc.primary_location_id,
                l.geometry
            FROM {trino_catalog}.{trino_schema}.secondary_timeseries st
            JOIN {trino_catalog}.{trino_schema}.location_crosswalks lc
            ON st.location_id = lc.secondary_location_id
            JOIN {trino_catalog}.{trino_schema}.locations l
            ON lc.primary_location_id = l.id
            WHERE {where_clause}
            ORDER BY st.value_time
            """
        else:
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
            print("Secondary query returned NO records - returning empty array")
            return JSONResponse(content=[], media_type="application/json")

        print(f"Query returned {len(df)} secondary timeseries records")

        format_start = time.time()
        df["value_time"] = pd.to_datetime(df["value_time"]).dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Convert reference_time to string, handle NaT as None
        if "reference_time" in df.columns:
            df["reference_time"] = pd.to_datetime(df["reference_time"]).dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            df["reference_time"] = df["reference_time"].replace("NaT", None)
        else:
            df["reference_time"] = None

        # Replace NaN with None for JSON serialization
        df["member"] = df["member"].where(pd.notna(df["member"]), None)
        df["value"] = df["value"].where(pd.notna(df["value"]), None)

        if f and f.lower() == "geojson":
            geojson = create_ogc_geojson_response(
                df,
                str(request.url),
                collection_id="secondary_timeseries",
            )

            return JSONResponse(
                content=geojson,
                headers={
                    "Content-Type": "application/geo+json",
                    "Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>",  # noqa: E501
                },
            )


        grouped = df.groupby(
            [
                "series_type",
                "primary_location_id",
                "reference_time",
                "configuration_name",
                "variable_name",
                "unit_name",
                "member",
            ],
            dropna=False  # Don't drop rows with NaN - important for retrospective data
        )

        print("Number of unique series:", len(grouped))
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
            
            # Handle NaN values from groupby keys - convert to None for JSON
            ref_time_value = None if pd.isna(reference_time) else reference_time
            member_value = None if pd.isna(member) else member
            
            timeseries_data = {
                "series_type": series_type,
                "primary_location_id": primary_location_id,
                "reference_time": ref_time_value,
                "configuration_name": configuration_name,
                "variable_name": variable_name,
                "unit_name": unit_name,
                "member": member_value,
                "timeseries": group[["value_time", "value"]].to_dict(orient="records"),
            }
            data.append(timeseries_data)

        format_time = time.time() - format_start
        print(f"Secondary formatting time: {format_time:.3f} seconds")

        print(data)

        return JSONResponse(content=data, media_type="application/json")

    except Exception as e:
        print(f"Secondary timeseries error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to load coverage: {str(e)}"
        ) from e
