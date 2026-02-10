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
    elevation: float
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


class DayPlanResponse(BaseModel):
    """Single day plan in a multi-day route."""
    day_number: int
    segments: List[RouteSegmentResponse]
    start_node: NodeResponse
    end_node: NodeResponse
    total_distance: float
    total_elevation_gain: float
    total_elevation_loss: float
    estimated_time: float
    difficulty: str
    overnight_stop: Optional[NodeResponse] = None


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

    # Multi-day planning
    multi_day: bool = False
    days: Optional[List[DayPlanResponse]] = None
    total_days: Optional[int] = None
    overnight_stops: Optional[List[NodeResponse]] = None

    # Recommendations
    equipment: List[EquipmentRecommendationResponse] = Field(default_factory=list)
    food: Optional[FoodRecommendationResponse] = None


class AreaResponse(BaseModel):
    """Hiking area information."""
    area_id: str
    name: str
    description: str
    country: str
    bbox: Optional[List[float]] = Field(None, description="Bounding box [min_lat, min_lon, max_lat, max_lon] (legacy, auto-calculated from routes)")
    elevation_range: List[int] = Field(..., description="[min_elevation, max_elevation] in meters")
    trail_count: Optional[int] = None
    peak_count: Optional[int] = None
    hut_count: Optional[int] = None
    routes: List[RouteInfo] = Field(default_factory=list)


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
