"""FastAPI dependencies for dependency injection."""

from functools import lru_cache

from app.services.estimation_service import EstimationService
from app.services.export_service import ExportService
from app.services.graph_service import GraphService
from app.services.planning_service import PlanningService
from app.services.recommendation_service import RecommendationService
from app.services.routing_service import RoutingService


@lru_cache()
def get_graph_service() -> GraphService:
    """Get or create GraphService instance."""
    return GraphService()


@lru_cache()
def get_routing_service() -> RoutingService:
    """Get or create RoutingService instance."""
    return RoutingService(get_graph_service())


@lru_cache()
def get_estimation_service() -> EstimationService:
    """Get or create EstimationService instance."""
    return EstimationService()


@lru_cache()
def get_planning_service() -> PlanningService:
    """Get or create PlanningService instance."""
    return PlanningService(get_graph_service(), get_estimation_service())


@lru_cache()
def get_recommendation_service() -> RecommendationService:
    """Get or create RecommendationService instance."""
    return RecommendationService()


@lru_cache()
def get_export_service() -> ExportService:
    """Get or create ExportService instance."""
    return ExportService()
