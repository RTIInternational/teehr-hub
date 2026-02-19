"""
OGC API - Features Part 3: Queryables endpoints.

Provides machine-readable schema for filterable properties in each collection.
Extends standard JSON Schema with x-teehr-role to indicate group_by vs metric
fields.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..database import get_trino_connection, sanitize_string

router = APIRouter()

# Known collections and their configurations
COLLECTION_CONFIGS = {
    "locations": {
        "table": "locations",
        "type": "feature",
        "description": "Geographic locations where observations are collected",
        "static_properties": {
            "id": {
                "title": "Location ID",
                "type": "string",
                "x-ogc-role": "id"
            },
            "name": {
                "title": "Location Name",
                "type": "string"
            },
            "geometry": {
                "$ref": "https://geojson.org/schema/Point.json",
                "x-ogc-role": "primary-geometry",
            },
        },
    },
    "primary_timeseries": {
        "table": "primary_timeseries",
        "type": "feature",
        "description": "Observed timeseries data at monitoring locations",
        "static_properties": {
            "location_id": {
                "title": "Location ID",
                "type": "string",
                "x-ogc-role": "id",
            },
            "value_time": {
                "title": "Value Time",
                "type": "string",
                "format": "date-time",
            },
            "value": {"title": "Observed Value", "type": "number"},
            "variable_name": {"title": "Variable/Parameter", "type": "string"},
            "configuration_name": {"title": "Configuration", "type": "string"},
            "unit_name": {"title": "Unit", "type": "string"},
        },
    },
    "secondary_timeseries": {
        "table": "secondary_timeseries",
        "type": "feature",
        "description": "Forecast/simulated timeseries data",
        "static_properties": {
            "location_id": {
                "title": "Location ID",
                "type": "string",
                "x-ogc-role": "id",
            },
            "value_time": {
                "title": "Value Time",
                "type": "string",
                "format": "date-time",
            },
            "reference_time": {
                "title": "Reference/Forecast Time",
                "type": "string",
                "format": "date-time",
            },
            "value": {"title": "Forecast Value", "type": "number"},
            "variable_name": {"title": "Variable/Parameter", "type": "string"},
            "configuration_name": {"title": "Configuration", "type": "string"},
            "member": {"title": "Ensemble Member", "type": "string"},
            "unit_name": {"title": "Unit", "type": "string"},
        },
    },
    "location_crosswalks": {
        "table": "location_crosswalks",
        "type": "feature",
        "description": "Crosswalk mapping between primary and secondary location identifiers",
        "static_properties": {
            "primary_location_id": {
                "title": "Primary Location ID",
                "type": "string",
            },
            "secondary_location_id": {
                "title": "Secondary Location ID",
                "type": "string",
            },
        },
    },
    "configurations": {
        "table": "configurations",
        "type": "feature",
        "description": "Configuration definitions for data sources",
        "static_properties": {
            "name": {
                "title": "Configuration Name",
                "type": "string",
                "x-ogc-role": "id",
            },
            "type": {
                "title": "Type",
                "type": "string",
            },
            "description": {
                "title": "Description",
                "type": "string",
            },
        },
    },
    "units": {
        "table": "units",
        "type": "feature",
        "description": "Unit definitions for measurements",
        "static_properties": {
            "name": {
                "title": "Unit Name",
                "type": "string",
                "x-ogc-role": "id",
            },
            "long_name": {
                "title": "Long Name",
                "type": "string",
            },
        },
    },
    "variables": {
        "table": "variables",
        "type": "feature",
        "description": "Variable definitions for measured quantities",
        "static_properties": {
            "name": {
                "title": "Variable Name",
                "type": "string",
                "x-ogc-role": "id",
            },
            "long_name": {
                "title": "Long Name",
                "type": "string",
            },
        },
    },
    "attributes": {
        "table": "attributes",
        "type": "feature",
        "description": "Attribute definitions for location attribute types",
        "static_properties": {
            "name": {
                "title": "Attribute Name",
                "type": "string",
                "x-ogc-role": "id",
            },
            "description": {
                "title": "Description",
                "type": "string",
            },
            "type": {
                "title": "Type",
                "type": "string",
            },
        },
    },
    "location_attributes": {
        "table": "location_attributes",
        "type": "feature",
        "description": "Attribute values associated with locations",
        "static_properties": {
            "location_id": {
                "title": "Location ID",
                "type": "string",
            },
            "attribute_name": {
                "title": "Attribute Name",
                "type": "string",
            },
            "value": {
                "title": "Value",
                "type": "string",
            },
        },
    },
}


def get_metrics_table_queryables(table_name: str) -> dict:
    """
    Build queryables schema for a metrics table by reading Iceberg properties.

    Returns JSON Schema with x-teehr-role extensions for group_by and metric
    fields.
    """
    try:
        conn = get_trino_connection()
        cur = conn.cursor()

        # Get table properties from Iceberg metadata
        query = f"""
            SELECT key, value FROM "{table_name}$properties"
            WHERE key IN ('metrics', 'group_by', 'description')
        """
        cur.execute(query)
        results = cur.fetchall()

        properties_meta = {}
        for key, value in results:
            if key in ("metrics", "group_by"):
                properties_meta[key] = [s.strip() for s in value.split(",")]
            else:
                properties_meta[key] = value

        group_by = properties_meta.get("group_by", [])
        metrics = properties_meta.get("metrics", [])
        description = properties_meta.get(
            "description", f"Metrics table: {table_name}"
        )

        # Build properties schema
        properties = {}

        # Add geometry (all metrics tables have it)
        if "geometry" in group_by:
            properties["geometry"] = {
                "$ref": "https://geojson.org/schema/Point.json",
                "x-ogc-role": "primary-geometry",
            }

        # Add group_by fields
        for field in group_by:
            # geometry is handled separately as a GeoJSON primary geometry;
            # avoid overwriting its schema with a generic string schema.
            if field == "geometry":
                continue
            properties[field] = {
                "title": field.replace("_", " ").title(),
                "type": "string",
                "x-teehr-role": "group_by",
            }
            # Mark primary_location_id as the OGC id
            if field == "primary_location_id":
                properties[field]["x-ogc-role"] = "id"

        # Add metric fields
        for field in metrics:
            properties[field] = {
                "title": field.replace("_", " ").title(),
                "type": "number",
                "x-teehr-role": "metric",
            }

        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"/collections/{table_name}/queryables",
            "type": "object",
            "title": table_name,
            "description": description,
            "properties": properties,
            # TEEHR extensions for quick access
            "x-teehr-group-by": group_by,
            "x-teehr-metrics": metrics,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load queryables for {table_name}: {str(e)}",
        ) from e


@router.get("/collections/{collection_id}/queryables")
async def get_collection_queryables(collection_id: str):
    """
    Get queryable properties for a collection (OGC API - Features Part 3).

    Returns a JSON Schema describing filterable properties. For metrics tables,
    includes x-teehr-role extensions indicating whether each field is a
    'group_by' dimension or a 'metric' value.

    Standard clients can use the JSON Schema for validation and UI generation.
    TEEHR-aware clients can use x-teehr-group-by and x-teehr-metrics for
    specialized handling.
    """
    # Check if it's a known static collection
    if collection_id in COLLECTION_CONFIGS:
        config = COLLECTION_CONFIGS[collection_id]
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"/collections/{collection_id}/queryables",
            "type": "object",
            "title": collection_id,
            "description": config["description"],
            "properties": config["static_properties"],
        }
        return JSONResponse(
            content=schema, media_type="application/schema+json"
        )

    # Assume it's a metrics table - try to load from Iceberg properties
    sanitized = sanitize_string(collection_id)
    schema = get_metrics_table_queryables(sanitized)

    return JSONResponse(content=schema, media_type="application/schema+json")

@router.get("/collections/{collection_id}/queryables/{property_name}/values")
async def get_queryable_values(collection_id: str, property_name: str):
    """
    Get distinct values for a queryable property (TEEHR extension).

    This is an extension to OGC API - Features Part 3 that returns the unique
    values available for a specific queryable property. Useful for populating
    filter dropdowns in UI applications.

    Returns a JSON array of distinct values.
    """
    # Validate and sanitize inputs
    sanitized_collection = sanitize_string(collection_id)
    sanitized_property = sanitize_string(property_name)

    if not sanitized_collection or not sanitized_property:
        raise HTTPException(status_code=400, detail="Invalid collection or property name")

    try:
        conn = get_trino_connection()
        cur = conn.cursor()

        # Query distinct values
        query = f"""
            SELECT DISTINCT {sanitized_property}
            FROM iceberg.teehr.{sanitized_collection}
            WHERE {sanitized_property} IS NOT NULL
            ORDER BY {sanitized_property}
        """
        cur.execute(query)
        results = cur.fetchall()

        values = [row[0] for row in results]

        return JSONResponse(
            content=values,
            media_type="application/json"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get values for {property_name}: {str(e)}",
        ) from e
