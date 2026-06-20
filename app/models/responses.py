"""API response models using Pydantic."""

from typing import List, Optional

from pydantic import BaseModel, Field


class WaypointInfo(BaseModel):
    """Waypoint information in route definition."""
    name: str
    lat: float
    lon: float
    elevation: int
    type: str
    required: bool = False
    facilities: Optional[List[str]] = None


class TrailheadInfo(BaseModel):
    """Trailhead information in route definition."""
    name: str
    lat: float
    lon: float
    elevation: int
    type: str = "trailhead"
    facilities: Optional[List[str]] = None


class RouteInfo(BaseModel):
    """Route information in area definition."""
    route_id: str
    name: str
    description: str
    days: int
    difficulty: str
    total_distance: float
    trailhead: TrailheadInfo
    waypoints: List[WaypointInfo] = Field(default_factory=list)
    estimated_time: str
    highlight: str


class NodeResponse(BaseModel):
    """Node information in API responses."""
    id: str
    type: str
    lat: float
    lon: float
    elevation: Optional[float] = 0.0
    name: Optional[str] = None
    amenities: List[str] = Field(default_factory=list)


class RouteSegmentResponse(BaseModel):
    """Route segment information in API responses."""
    start_node: NodeResponse
    end_node: NodeResponse
    distance: float = Field(..., description="Distance in km")
    elevation_gain: float = Field(..., description="Elevation gain in meters")
    elevation_loss: float = Field(..., description="Elevation loss in meters")
    estimated_time: float = Field(..., description="Estimated time in hours")
    difficulty: str
    trail_name: Optional[str] = None
    geometry: List[List[float]] = Field(default_factory=list, description="Path geometry as [[lat, lon], ...]")


class TimeEstimate(BaseModel):
    """Time estimates with optimistic/normal/conservative scenarios."""
    optimistic: float = Field(..., description="Optimistic estimate in hours")
    normal: float = Field(..., description="Normal estimate in hours")
    conservative: float = Field(..., description="Conservative estimate in hours")



class EquipmentRecommendationResponse(BaseModel):
    """Equipment recommendations."""
    category: str
    items: List[str]


class FoodRecommendationResponse(BaseModel):
    """Food and water recommendations."""
    daily_calories: int
    total_calories: int
    meals_per_day: int
    daily_water_liters: float
    notes: List[str] = Field(default_factory=list)


class LegResponse(BaseModel):
    """One user-defined leg (between two selected points)."""
    start_node: NodeResponse
    end_node: NodeResponse
    distance: float
    elevation_gain: float
    elevation_loss: float
    estimated_time: float  # normal estimate in hours
    segment_start: int  # index into route.segments (inclusive)
    segment_end: int    # index into route.segments (inclusive)


class DayPlanResponse(BaseModel):
    """One day's plan within a multi-day route."""
    day: int
    overnight_stop: Optional[NodeResponse] = None  # None for the last day
    segments: List[RouteSegmentResponse]
    distance: float
    elevation_gain: float
    elevation_loss: float
    estimated_time: TimeEstimate


class RouteResponse(BaseModel):
    """Complete route information."""
    route_id: str
    area_id: str
    segments: List[RouteSegmentResponse]
    total_distance: float = Field(..., description="Total distance in km")
    total_elevation_gain: float = Field(..., description="Total elevation gain in meters")
    total_elevation_loss: float = Field(..., description="Total elevation loss in meters")
    estimated_time: TimeEstimate
    difficulty: str
    is_loop: bool
    waypoints: List[NodeResponse] = Field(default_factory=list)
    legs: List[LegResponse] = Field(default_factory=list)
    day_plans: List[DayPlanResponse] = Field(default_factory=list)

    # Recommendations
    equipment: List[EquipmentRecommendationResponse] = Field(default_factory=list)
    food: Optional[FoodRecommendationResponse] = None


class PointResponse(BaseModel):
    """Individual point (trailhead, peak, hut, etc.) in an area."""
    id: str
    name: str
    type: str  # trailhead, peak, hut, waypoint
    lat: float
    lon: float
    elevation: float
    description: Optional[str] = None
    facilities: List[str] = Field(default_factory=list)
    capacity: Optional[int] = None


class RecommendedRouteResponse(BaseModel):
    """Recommended route template."""
    route_id: str
    name: str
    description: str
    days: int
    difficulty: str
    estimated_distance: Optional[float] = None
    estimated_time: Optional[str] = None
    point_sequence: List[str]  # List of point IDs
    highlight: Optional[str] = None


class AreaResponse(BaseModel):
    """Hiking area information."""
    area_id: str
    name: str
    description: str
    country: str
    elevation_range: List[int] = Field(..., description="[min_elevation, max_elevation] in meters")
    features: List[str] = Field(default_factory=list)
    points: List[PointResponse] = Field(default_factory=list)
    recommended_routes: List[RecommendedRouteResponse] = Field(default_factory=list)

    # Legacy fields (optional, for backward compatibility)
    bbox: Optional[List[float]] = Field(None, description="Bounding box [min_lat, min_lon, max_lat, max_lon]")
    trail_count: Optional[int] = None
    peak_count: Optional[int] = None
    hut_count: Optional[int] = None


class AreaListResponse(BaseModel):
    """List of available hiking areas."""
    areas: List[AreaResponse]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
