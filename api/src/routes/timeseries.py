"""
Timeseries endpoints (OGC API - GeoJSON and TEEHR TS).
"""

import time
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..database import execute_query, sanitize_string, trino_catalog, trino_schema
from .utils import create_ogc_geojson_response

router = APIRouter()


@router.get("/collections/primary_timeseries/items")
async def get_primary_timeseries_items(
    request: Request,
    primary_location_id: list[str] = Query(
        ..., description="Primary location ID(s) - can be specified multiple times"
    ),
    datetime_range: str | None = Query(
        None,
        alias="datetime",
        description="ISO 8601 datetime interval (e.g., 2020-01-01/2020-12-31)",
    ),
    variable_name: str | None = Query(None, description="Variable name filter"),
    configuration_name: str | None = Query(None, description="Configuration name filter"),
    f: str | None = Query("json", description="Output format: json or geojson"),
):
    """Get primary timeseries (observations) for a location.

    Returns array of timeseries objects with streamflow data.
    """
    try:
        print(f"Primary timeseries called with: primary_location_id={primary_location_id}, datetime={datetime_range}, variable_name={variable_name}, configuration_name={configuration_name}")
        safe_location_ids = [f"'{sanitize_string(loc)}'" for loc in primary_location_id]
        where_conditions = [f"location_id IN ({', '.join(safe_location_ids)})"]

        # Parse datetime as ISO 8601 interval (standard OGC format)
        if datetime_range:
            if "/" in datetime_range:
                start_str, end_str = datetime_range.split("/", 1)
            else:
                start_str = end_str = datetime_range

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
        if variable_name:
            safe_variable = sanitize_string(variable_name)
            where_conditions.append(f"variable_name = '{safe_variable}'")

        # Filter by configuration
        if configuration_name:
            safe_configuration = sanitize_string(configuration_name)
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
            status_code=500, detail=f"Failed to load primary timeseries: {str(e)}"
        ) from e


@router.get("/collections/secondary_timeseries/items")
async def get_secondary_timeseries_items(
    request: Request,
    primary_location_id: list[str] | None = Query(None, description="Primary location ID(s) - can be specified multiple times"),
    secondary_location_id: list[str] | None = Query(None, description="Secondary location ID(s) - can be specified multiple times"),
    datetime_range: str | None = Query(
        None,
        alias="datetime",
        description="ISO 8601 datetime interval (e.g., 2020-01-01/2020-12-31)",
    ),
    reference_time: str | None = Query(
        None,
        description="ISO 8601 reference time interval (e.g., 2020-01-01/2020-12-31)",  # noqa: E501
    ),
    variable_name: str | None = Query(None, description="Variable name filter"),
    configuration_name: str | None = Query(None, description="Configuration name filter"),
    f: str | None = Query("json", description="Output format: json or geojson"),
):
    """Get secondary timeseries (model outputs/forecasts) for a location.

    Supports filtering by:
    - datetime: ISO 8601 interval for value_time (e.g., 2020-01-01/2020-12-31)
    - reference_time: ISO 8601 interval for reference_time (e.g., 2025-11-01/..)
    - variable_name: Variable name (e.g., streamflow_hourly_inst)
    - configuration_name: Configuration name (e.g., nwm30_medium_range)

    Returns array of timeseries objects, one per unique combination of
    reference_time, configuration, variable, and member.
    """
    try:
        print(f"Secondary timeseries called with: primary_location_id={primary_location_id}, secondary_location_id={secondary_location_id}, datetime={datetime_range}, reference_time={reference_time}, variable_name={variable_name}, configuration_name={configuration_name}")
        
        where_conditions = []
        
        # Handle location filtering - either primary or secondary
        if primary_location_id and secondary_location_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot filter by both primary_location_id and secondary_location_id. Use one or the other."
            )
        elif primary_location_id:
            safe_location_ids = [f"'{sanitize_string(loc)}'" for loc in primary_location_id]
            where_conditions.append(f"lc.primary_location_id IN ({', '.join(safe_location_ids)})")
        elif secondary_location_id:
            safe_location_ids = [f"'{sanitize_string(loc)}'" for loc in secondary_location_id]
            where_conditions.append(f"lc.secondary_location_id IN ({', '.join(safe_location_ids)})")
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide either primary_location_id or secondary_location_id"
            )

        # Parse datetime as ISO 8601 interval (standard OGC format)
        if datetime_range:
            if "/" in datetime_range:
                start_str, end_str = datetime_range.split("/", 1)
            else:
                start_str = end_str = datetime_range

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
        if variable_name:
            safe_variable = sanitize_string(variable_name)
            where_conditions.append(f"st.variable_name = '{safe_variable}'")

        # Filter by configuration
        if configuration_name:
            safe_configuration = sanitize_string(configuration_name)
            where_conditions.append(f"st.configuration_name = '{safe_configuration}'")
        where_clause = " AND ".join(where_conditions)

        # Build query based on format
        if f and f.lower() == "geojson":
            query = f"""
            SELECT
                st.value_time, st.value, st.configuration_name, st.variable_name,
                st.unit_name, st.member, st.reference_time,
                lc.primary_location_id, lc.secondary_location_id,
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
                lc.primary_location_id, 'secondary' as series_type, lc.secondary_location_id
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
                "secondary_location_id",
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
            secondary_location_id,
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
                "secondary_location_id": secondary_location_id,
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
            status_code=500, detail=f"Failed to load secondary timeseries: {str(e)}"
        ) from e
