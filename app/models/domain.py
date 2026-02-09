"""Core domain models for hiking routes and trail networks."""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import List, Optional, Tuple


class NodeType(Enum):
    """Types of nodes in the trail network."""
    TRAILHEAD = "trailhead"
    INTERSECTION = "intersection"
    PEAK = "peak"
    HUT = "hut"
    CAMPSITE = "campsite"
    WATER_SOURCE = "water_source"
    VIEWPOINT = "viewpoint"
    GENERIC = "generic"


class TrailDifficulty(IntEnum):
    """Trail difficulty levels based on SAC scale."""
    EASY = 1  # T1: hiking, sac_scale=hiking
    MODERATE = 2  # T2: mountain_hiking
    DIFFICULT = 3  # T3: demanding_mountain_hiking
    EXPERT = 4  # T4+: alpine_hiking


class FitnessLevel(Enum):
    """Hiker fitness levels."""
    BEGINNER = "beginner"
    MODERATE = "moderate"
    EXPERT = "expert"


@dataclass
class Node:
    """A node in the trail network graph."""
    id: str
    node_type: NodeType
    lat: float
    lon: float
    elevation: float  # meters
    name: Optional[str] = None
    amenities: List[str] = field(default_factory=list)  # ["water", "shelter", "camping"]

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Node):
            return self.id == other.id
        return False


@dataclass
class Edge:
    """An edge (trail segment) in the trail network graph."""
    source: str  # node id
    target: str  # node id
    distance: float  # meters
    elevation_gain: float  # meters (positive)
    elevation_loss: float  # meters (positive)
    difficulty: TrailDifficulty
    surface: str = "unpaved"
    trail_name: Optional[str] = None
    geometry: List[Tuple[float, float]] = field(default_factory=list)  # [(lat, lon), ...]
    
    # Popularity indicators
    popularity_score: float = 1.0  # 0.5-2.0, higher = more popular
    gps_trace_count: int = 0  # Number of GPS traces crossing this edge
    osm_popularity: float = 1.0  # Original OSM-based popularity
    trail_visibility: Optional[str] = None  # OSM: excellent, good, intermediate, bad, horrible, no
    route_ref: Optional[str] = None  # Official route reference (e.g., "GR20", "玉山主峰線")
    osm_tags: dict = field(default_factory=dict)  # Raw OSM tags for additional analysis


@dataclass
class RouteSegment:
    """A segment of a hiking route between two nodes."""
    start_node: Node
    end_node: Node
    edge: Edge
    distance: float  # km
    elevation_gain: float  # meters
    elevation_loss: float  # meters
    estimated_time: float  # hours
    difficulty: TrailDifficulty
    geometry: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class Route:
    """A complete hiking route."""
    route_id: str
    segments: List[RouteSegment]
    total_distance: float  # km
    total_elevation_gain: float  # meters
    total_elevation_loss: float  # meters
    estimated_time: float  # hours
    difficulty: TrailDifficulty
    waypoints: List[Node]  # peaks, huts, etc.
    is_loop: bool = False
    area_id: Optional[str] = None


@dataclass
class DayPlan:
    """A single day's plan in a multi-day route."""
    day_number: int
    segments: List[RouteSegment]
    start_node: Node
    end_node: Node
    total_distance: float  # km
    total_elevation_gain: float  # meters
    total_elevation_loss: float  # meters
    estimated_time: float  # hours
    difficulty: TrailDifficulty
    overnight_stop: Optional[Node] = None  # hut or campsite


@dataclass
class MultiDayPlan:
    """A multi-day hiking plan."""
    route: Route
    days: List[DayPlan]
    total_days: int
    overnight_stops: List[Node]


@dataclass
class EquipmentRecommendation:
    """Equipment recommendations for a route."""
    category: str  # "essential", "recommended", "optional"
    items: List[str]


@dataclass
class FoodRecommendation:
    """Food and water recommendations."""
    daily_calories: int
    total_calories: int
    meals_per_day: int
    daily_water_liters: float
    notes: List[str] = field(default_factory=list)
