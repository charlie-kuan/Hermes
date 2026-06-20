"""API request models using Pydantic."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class RoutePlanRequest(BaseModel):
    """Request to plan a hiking route."""
    area_id: str = Field(..., description="ID of the hiking area")

    # Start/End Points
    start_lat: float = Field(..., ge=-90, le=90, description="Start latitude")
    start_lon: float = Field(..., ge=-180, le=180, description="Start longitude")
    end_lat: Optional[float] = Field(None, ge=-90, le=90, description="End latitude (optional for loops)")
    end_lon: Optional[float] = Field(None, ge=-180, le=180, description="End longitude (optional for loops)")

    start_name: Optional[str] = Field(None, description="Display name for the start point")
    end_name: Optional[str] = Field(None, description="Display name for the end point")

    # Route Type
    loop_route: bool = Field(default=False, description="Create a loop route returning to start")

    # Via Points (optional)
    via_points: Optional[List[dict]] = Field(
        None,
        description="Waypoints to visit (list of {lat, lon})"
    )

    # Constraints
    max_distance: Optional[float] = Field(None, gt=0, description="Maximum distance in km")
    required_waypoints: Optional[List[str]] = Field(
        None,
        description="Required waypoint types (peak, hut, etc.)"
    )

    # Overnight stops (shelters/huts where hiker will spend the night)
    overnight_stops: Optional[List[dict]] = Field(
        None,
        description="Shelter stops for multi-day routes (list of {lat, lon, name})"
    )

    # Hiker Parameters
    hiker_fitness: str = Field(default="moderate", description="Fitness level: beginner, moderate, expert")
    pack_weight_kg: Optional[float] = Field(12.0, ge=0, le=50, description="Backpack weight in kg")

    # Preferences
    @field_validator("hiker_fitness")
    @classmethod
    def validate_fitness(cls, v: str) -> str:
        if v not in ["beginner", "moderate", "expert"]:
            raise ValueError("hiker_fitness must be 'beginner', 'moderate', or 'expert'")
        return v


class TimeEstimateRequest(BaseModel):
    """Request to re-estimate time for an existing route with different parameters."""
    route_id: str = Field(..., description="ID of the route to re-estimate")
    hiker_fitness: str = Field(default="moderate", description="Fitness level")
    pack_weight_kg: float = Field(default=12.0, ge=0, le=50, description="Backpack weight in kg")

    @field_validator("hiker_fitness")
    @classmethod
    def validate_fitness(cls, v: str) -> str:
        if v not in ["beginner", "moderate", "expert"]:
            raise ValueError("hiker_fitness must be 'beginner', 'moderate', or 'expert'")
        return v


class ExportFormat(BaseModel):
    """Export format options."""
    format: str = Field(default="gpx", description="Export format: gpx or geojson")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        if v not in ["gpx", "geojson"]:
            raise ValueError("format must be 'gpx' or 'geojson'")
        return v
