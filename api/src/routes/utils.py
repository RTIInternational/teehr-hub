"""
Utility functions for OGC API compliance.
"""

import re
from datetime import UTC, datetime


def parse_subset_parameter(subset_params: list[str]) -> dict[str, tuple]:
    """Parse OGC API subset parameters for non-temporal dimensions.

    Supports single-value subset syntax:
    - subset=location("usgs-01347000")
    - subset=parameter("streamflow")
    - subset=configuration("nwm30")

    For temporal parameters, use the standard OGC datetime parameter
    with ISO 8601 intervals (e.g., datetime=2020-01-01/2020-12-31).

    Returns:
        dict: {dimension_name: (value, None)}
    """
    subsets = {}

    def strip_quotes(s):
        """Strip surrounding quotes from a string."""
        s = s.strip()
        if (s.startswith('"') and s.endswith('"')) or (
            s.startswith("'") and s.endswith("'")
        ):
            return s[1:-1]
        return s

    for subset in subset_params:
        # Parse: dimensionName(value)
        match = re.match(r"(\w+)\((.*)\)", subset)
        if not match:
            continue

        dimension, values = match.groups()
        value = strip_quotes(values)
        subsets[dimension] = (value, None)

    return subsets


def parse_datetime_parameter(datetime_param: str | None) -> tuple:
    """Parse OGC datetime parameter (ISO 8601).

    Supports:
    - Single datetime: "2020-01-01T00:00:00Z"
    - Interval: "2020-01-01T00:00:00Z/2020-12-31T23:59:59Z"
    - Open start: "../2020-12-31T23:59:59Z"
    - Open end: "2020-01-01T00:00:00Z/.."

    Returns:
        tuple: (start_datetime, end_datetime) or (None, None)
    """
    if not datetime_param:
        return None, None

    # Handle interval (with slash)
    if "/" in datetime_param:
        parts = datetime_param.split("/")
        start_str, end_str = parts[0], parts[1]

        if start_str == "..":
            start_dt = None
        else:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))

        if end_str == "..":
            end_dt = None
        else:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        return start_dt, end_dt
    else:
        # Single datetime - treat as exact match
        dt = datetime.fromisoformat(datetime_param.replace("Z", "+00:00"))
        return dt, dt


def parse_coords_parameter(coords: str | None) -> dict | None:
    """Parse OGC coords parameter.

    Supports WKT-like syntax:
    - POINT(lon lat)
    - POLYGON((lon lat, lon lat, ...))

    Returns:
        dict with 'type' and 'coordinates', or None if coords is empty
    """
    if not coords:
        return None

    coords = coords.strip()

    if coords.upper().startswith("POINT"):
        # Extract coordinates from POINT(lon lat)
        coords_str = coords[coords.index("(") + 1 : coords.index(")")].strip()
        lon, lat = map(float, coords_str.split())
        return {"type": "Point", "lon": lon, "lat": lat}

    # Add more geometry types as needed
    return None


def create_ogc_geojson_response(
    geojson: dict,
    request_url: str,
    number_matched: int | None = None,
    collection_id: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    """Add OGC-compliant metadata and links to a GeoJSON response.

    Args:
        geojson: Base GeoJSON FeatureCollection
        request_url: URL of the current request
        number_matched: Total number of features matching query
        collection_id: Collection identifier for link generation
        limit: Current page size for pagination links
        offset: Current offset for pagination links
    """
    # Add timestamp
    geojson["timeStamp"] = datetime.now(UTC).isoformat()

    # Add number fields
    number_returned = len(geojson.get("features", []))
    geojson["numberReturned"] = number_returned

    if number_matched is not None:
        geojson["numberMatched"] = number_matched
    else:
        geojson["numberMatched"] = number_returned

    # Parse base URL for pagination links
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(request_url)
    query_params = parse_qs(parsed.query)

    # Add links
    links = [
        {
            "href": request_url,
            "rel": "self",
            "type": "application/geo+json",
            "title": "This document",
        }
    ]

    if collection_id:
        links.append(
            {
                "href": f"/collections/{collection_id}",
                "rel": "collection",
                "type": "application/json",
                "title": "The collection document",
            }
        )

    # Add pagination links if applicable
    if limit is not None and offset is not None:
        # Next link (if we returned a full page)
        if number_returned == limit:
            next_offset = offset + limit
            query_params["offset"] = [str(next_offset)]
            query_params["limit"] = [str(limit)]
            next_query = urlencode({k: v[0] for k, v in query_params.items()})
            next_url = urlunparse(parsed._replace(query=next_query))
            links.append(
                {
                    "href": next_url,
                    "rel": "next",
                    "type": "application/geo+json",
                    "title": "Next page",
                }
            )

        # Previous link (if not on first page)
        if offset > 0:
            prev_offset = max(0, offset - limit)
            query_params["offset"] = [str(prev_offset)]
            query_params["limit"] = [str(limit)]
            prev_query = urlencode({k: v[0] for k, v in query_params.items()})
            prev_url = urlunparse(parsed._replace(query=prev_query))
            links.append(
                {
                    "href": prev_url,
                    "rel": "prev",
                    "type": "application/geo+json",
                    "title": "Previous page",
                }
            )

    geojson["links"] = links

    return geojson


def create_coveragejson_timeseries(
    timeseries_data: list, location_id: str, location_coords: tuple | None = None
) -> dict:
    """Convert timeseries data to CoverageJSON format (OGC EDR standard).

    Args:
        timeseries_data: List of timeseries objects from database
        location_id: Location identifier
        location_coords: Optional (lon, lat) tuple for the location

    Returns:
        CoverageJSON Coverage object
    """
    if not timeseries_data:
        return {
            "type": "Coverage",
            "domain": {"type": "Domain", "axes": {"t": {"values": []}}},
            "parameters": {},
            "ranges": {},
        }

    # Group by parameter/variable AND reference_time (for forecasts) AND member
    # This preserves separate traces for each forecast issue time and ensemble member
    parameters_data = {}
    for series in timeseries_data:
        variable_name = series.get("variable_name", "unknown")
        reference_time = series.get("reference_time")
        configuration = series.get("configuration_name", "")
        member = series.get("member")
        
        # Ensure reference_time is a string (handle Timestamp objects)
        if reference_time is not None and reference_time != "null":
            if hasattr(reference_time, 'strftime'):
                reference_time = reference_time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                reference_time = str(reference_time)
        elif reference_time == "null":
            reference_time = None
            
        # Ensure member is a string
        if member is not None and member != "null":
            member = str(member)
        elif member == "null":
            member = None
        
        # Create unique key for each series (variable + reference_time + member)
        key_parts = [variable_name]
        label_parts = [variable_name]
        
        if reference_time is not None:
            key_parts.append(str(reference_time))
            label_parts.append(f"ref: {reference_time}")
            
        if member is not None:
            key_parts.append(str(member))
            label_parts.append(f"member: {member}")
            
        param_key = "_".join(key_parts)
        param_label = variable_name if len(label_parts) == 1 else f"{variable_name} ({', '.join(label_parts[1:])})"
            
        if param_key not in parameters_data:
            parameters_data[param_key] = {
                "unit": series.get("unit_name", ""),
                "configuration": configuration,
                "variable_name": variable_name,
                "reference_time": reference_time,
                "member": member,
                "label": param_label,
                "times": [],
                "values": [],
            }

        # Add timeseries points
        for point in series.get("timeseries", []):
            parameters_data[param_key]["times"].append(point["value_time"])
            parameters_data[param_key]["values"].append(point["value"])

    # Build CoverageJSON structure
    # Get all unique times across all parameters
    all_times = sorted(
        {
            time
            for param_data in parameters_data.values()
            for time in param_data["times"]
        }
    )

    # Build domain
    domain = {"type": "Domain", "axes": {"t": {"values": all_times}}}

    # Add spatial coordinates if available
    if location_coords:
        domain["axes"]["x"] = {"values": [location_coords[0]]}
        domain["axes"]["y"] = {"values": [location_coords[1]]}

    # Build parameters
    parameters = {}
    ranges = {}

    for param_key, param_data in parameters_data.items():
        parameters[param_key] = {
            "type": "Parameter",
            "description": {"en": f"{param_data['label']} - {param_data['configuration']}"},
            "unit": {"label": {"en": param_data["unit"]}, "symbol": param_data["unit"]},
            "observedProperty": {
                "id": param_data["variable_name"],
                "label": {"en": param_data["variable_name"]}
            },
            # Include all grouping fields for frontend consumption
            "primaryLocationId": location_id,
            "referenceTime": param_data.get("reference_time"),
            "configurationName": param_data.get("configuration"),
            "variableName": param_data.get("variable_name"),
            "unitName": param_data.get("unit"),
            "member": param_data.get("member"),
        }

        # Build ranges - align values with domain times
        time_value_map = dict(
            zip(param_data["times"], param_data["values"], strict=False)
        )
        aligned_values = [time_value_map.get(t, None) for t in all_times]

        ranges[param_key] = {
            "type": "NdArray",
            "dataType": "float",
            "axisNames": ["t"],
            "shape": [len(all_times)],
            "values": aligned_values,
        }

    return {
        "type": "Coverage",
        "domain": domain,
        "parameters": parameters,
        "ranges": ranges,
        # Include location at Coverage level as well
        "primaryLocationId": location_id,
    }
