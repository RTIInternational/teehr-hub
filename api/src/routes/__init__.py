"""
Main router combining all sub-routers.
"""

from fastapi import APIRouter

from . import locations, metrics, ogc_foundation, queryables, timeseries

# Create main router
router = APIRouter()

# Include all sub-routers
router.include_router(ogc_foundation.router, tags=["OGC API"])
router.include_router(locations.router, tags=["Locations"])
router.include_router(metrics.router, tags=["Metrics"])
router.include_router(timeseries.router, tags=["Timeseries"])
router.include_router(queryables.router, tags=["Queryables"])

# Export for backward compatibility
__all__ = ["router"]
