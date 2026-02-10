"""Route planning endpoint handlers."""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from loguru import logger

from app.api.dependencies import (
    get_estimation_service,
    get_export_service,
    get_graph_service,
    get_planning_service,
    get_recommendation_service,
    get_routing_service
)
from app.api.routes.areas import load_areas
from app.exceptions import (
    GraphNotFoundError,
    InvalidAreaError,
    NoValidPathError,
    RouteNotFoundError
)
from app.models.domain import (
    DayPlan,
    EquipmentRecommendation,
    FoodRecommendation,
    MultiDayPlan,
    Node,
    Route,
    RouteSegment
)
from app.models.requests import RoutePlanRequest, TimeEstimateRequest
from app.models.responses import (
    DayPlanResponse,
    EquipmentRecommendationResponse,
    FoodRecommendationResponse,
    NodeResponse,
    RouteResponse,
    RouteSegmentResponse,
    TimeEstimate
)
from app.services.estimation_service import EstimationService
from app.services.export_service import ExportService
from app.services.graph_service import GraphService
from app.services.planning_service import PlanningService
from app.services.recommendation_service import RecommendationService
from app.services.routing_service import RoutingService

router = APIRouter()

# In-memory route cache (in production, use Redis or similar)
route_cache: Dict[str, Route] = {}
multi_day_cache: Dict[str, MultiDayPlan] = {}


def node_to_response(node: Node) -> NodeResponse:
    """Convert Node to NodeResponse."""
    return NodeResponse(
        id=node.id,
        type=node.node_type.value,
        lat=node.lat,
        lon=node.lon,
        elevation=node.elevation,
        name=node.name,
        amenities=node.amenities
    )


def segment_to_response(segment: RouteSegment) -> RouteSegmentResponse:
    """Convert RouteSegment to RouteSegmentResponse."""
    return RouteSegmentResponse(
        start_node=node_to_response(segment.start_node),
        end_node=node_to_response(segment.end_node),
        distance=segment.distance,
        elevation_gain=segment.elevation_gain,
        elevation_loss=segment.elevation_loss,
        estimated_time=segment.estimated_time,
        difficulty=segment.difficulty.name.lower(),
        trail_name=segment.edge.trail_name
    )


def day_plan_to_response(day: DayPlan) -> DayPlanResponse:
    """Convert DayPlan to DayPlanResponse."""
    return DayPlanResponse(
        day_number=day.day_number,
        segments=[segment_to_response(s) for s in day.segments],
        start_node=node_to_response(day.start_node),
        end_node=node_to_response(day.end_node),
        total_distance=day.total_distance,
        total_elevation_gain=day.total_elevation_gain,
        total_elevation_loss=day.total_elevation_loss,
        estimated_time=day.estimated_time,
        difficulty=day.difficulty.name.lower(),
        overnight_stop=node_to_response(day.overnight_stop) if day.overnight_stop else None
    )


@router.post("/routes/plan", response_model=RouteResponse, tags=["Routes"])
async def plan_route(
    request: RoutePlanRequest,
    graph_service: GraphService = Depends(get_graph_service),
    routing_service: RoutingService = Depends(get_routing_service),
    estimation_service: EstimationService = Depends(get_estimation_service),
    planning_service: PlanningService = Depends(get_planning_service),
    recommendation_service: RecommendationService = Depends(get_recommendation_service)
):
    """
    Plan a hiking route.

    Creates a complete route plan with time estimates, multi-day splits (if requested),
    and equipment/food recommendations.

    Args:
        request: Route planning parameters

    Returns:
        Complete route information with segments, time estimates, and recommendations
    """
    logger.info(f"Planning route for area: {request.area_id}")

    # Load area metadata
    areas = load_areas()
    area_data = None
    for area in areas:
        if area['area_id'] == request.area_id:
            area_data = area
            break

    if not area_data:
        raise HTTPException(status_code=404, detail=f"Area {request.area_id} not found")

    try:
        # Get or build graph - bbox will be auto-calculated from routes
        graph = graph_service.get_or_build_graph(
            request.area_id, 
            area_data=area_data
        )

        # Find start node
        start_node_id = graph_service.find_nearest_node(
            graph, request.start_lat, request.start_lon
        )

        if not start_node_id:
            raise HTTPException(
                status_code=400,
                detail=f"No trail found within 2km of start coordinates ({request.start_lat:.5f}, {request.start_lon:.5f}). "
                       f"Please select a location closer to the trail network."
            )

        # Find end node (if not loop)
        end_node_id = None
        if not request.loop_route and request.end_lat and request.end_lon:
            end_node_id = graph_service.find_nearest_node(
                graph, request.end_lat, request.end_lon
            )

            if not end_node_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"No trail found within 2km of end coordinates ({request.end_lat:.5f}, {request.end_lon:.5f}). "
                           f"Please select a location closer to the trail network."
                )

        # Convert via points to node IDs
        via_node_ids = None
        if request.via_points:
            via_node_ids = []
            for via_point in request.via_points:
                via_lat = via_point.get('lat')
                via_lon = via_point.get('lon')
                if via_lat and via_lon:
                    via_id = graph_service.find_nearest_node(graph, via_lat, via_lon)
                    if via_id:
                        via_node_ids.append(via_id)

        # Set preferences
        preferences = None
        if request.avoid_difficult:
            preferences = {'distance': 0.8, 'elevation': 0.5, 'difficulty': 1.5}

        # Plan the route
        route = routing_service.plan_route(
            graph,
            start_node_id,
            end_node_id,
            via_nodes=via_node_ids,
            preferences=preferences,
            avoid_difficult=request.avoid_difficult
        )

        route.area_id = request.area_id

        # Estimate times for all segments
        route = estimation_service.estimate_all_segments(
            route,
            request.hiker_fitness,
            request.pack_weight_kg
        )

        # Get time estimates
        optimistic, normal, conservative = estimation_service.estimate_route(
            route,
            request.hiker_fitness,
            request.pack_weight_kg
        )

        time_estimate = TimeEstimate(
            optimistic=optimistic,
            normal=normal,
            conservative=conservative
        )

        # Multi-day planning
        multi_day_plan = None
        if request.multi_day and request.target_hours_per_day:
            multi_day_plan = planning_service.split_into_days(
                route,
                graph,
                request.target_hours_per_day,
                request.prefer_huts,
                request.hiker_fitness,
                request.pack_weight_kg
            )

            # Cache multi-day plan
            multi_day_cache[route.route_id] = multi_day_plan

        # Generate recommendations
        equipment = recommendation_service.recommend_equipment(
            route, multi_day_plan
        )

        food = recommendation_service.recommend_food(
            route, multi_day_plan, request.hiker_fitness, request.pack_weight_kg
        )

        # Cache route
        route_cache[route.route_id] = route

        # Build response
        response = RouteResponse(
            route_id=route.route_id,
            area_id=route.area_id,
            segments=[segment_to_response(s) for s in route.segments],
            total_distance=route.total_distance,
            total_elevation_gain=route.total_elevation_gain,
            total_elevation_loss=route.total_elevation_loss,
            estimated_time=time_estimate,
            difficulty=route.difficulty.name.lower(),
            is_loop=route.is_loop,
            waypoints=[node_to_response(w) for w in route.waypoints],
            multi_day=request.multi_day,
            equipment=[
                EquipmentRecommendationResponse(
                    category=e.category,
                    items=e.items
                ) for e in equipment
            ],
            food=FoodRecommendationResponse(
                daily_calories=food.daily_calories,
                total_calories=food.total_calories,
                meals_per_day=food.meals_per_day,
                daily_water_liters=food.daily_water_liters,
                notes=food.notes
            )
        )

        # Add multi-day details
        if multi_day_plan:
            response.days = [day_plan_to_response(day) for day in multi_day_plan.days]
            response.total_days = multi_day_plan.total_days
            response.overnight_stops = [
                node_to_response(stop) for stop in multi_day_plan.overnight_stops
            ]

        logger.info(f"Created route {route.route_id}: {route.total_distance:.1f}km, {normal:.1f}h")

        return response

    except HTTPException:
        # Re-raise HTTPException without wrapping it
        raise
    except NoValidPathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GraphNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error planning route: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error planning route: {str(e)}")


@router.get("/routes/{route_id}", response_model=RouteResponse, tags=["Routes"])
async def get_route(
    route_id: str,
    estimation_service: EstimationService = Depends(get_estimation_service)
):
    """
    Get a previously planned route by ID.

    Args:
        route_id: Route identifier

    Returns:
        Complete route information
    """
    if route_id not in route_cache:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")

    route = route_cache[route_id]
    multi_day_plan = multi_day_cache.get(route_id)

    # Get time estimates
    optimistic, normal, conservative = estimation_service.estimate_route(route)

    time_estimate = TimeEstimate(
        optimistic=optimistic,
        normal=normal,
        conservative=conservative
    )

    # Build response
    response = RouteResponse(
        route_id=route.route_id,
        area_id=route.area_id or "unknown",
        segments=[segment_to_response(s) for s in route.segments],
        total_distance=route.total_distance,
        total_elevation_gain=route.total_elevation_gain,
        total_elevation_loss=route.total_elevation_loss,
        estimated_time=time_estimate,
        difficulty=route.difficulty.name.lower(),
        is_loop=route.is_loop,
        waypoints=[node_to_response(w) for w in route.waypoints],
        multi_day=multi_day_plan is not None
    )

    # Add multi-day details
    if multi_day_plan:
        response.days = [day_plan_to_response(day) for day in multi_day_plan.days]
        response.total_days = multi_day_plan.total_days
        response.overnight_stops = [
            node_to_response(stop) for stop in multi_day_plan.overnight_stops
        ]

    return response


@router.get("/routes/{route_id}/export", tags=["Routes"])
async def export_route(
    route_id: str,
    format: str = Query("gpx", regex="^(gpx|geojson)$"),
    export_service: ExportService = Depends(get_export_service)
):
    """
    Export a route to GPX or GeoJSON format.

    Args:
        route_id: Route identifier
        format: Export format (gpx or geojson)

    Returns:
        Route file in requested format
    """
    if route_id not in route_cache:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")

    route = route_cache[route_id]

    try:
        if format == "gpx":
            content = export_service.export_to_gpx(route)
            media_type = "application/gpx+xml"
            filename = f"route_{route_id[:8]}.gpx"
        else:  # geojson
            content = export_service.export_to_geojson(route)
            media_type = "application/geo+json"
            filename = f"route_{route_id[:8]}.geojson"

        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        logger.error(f"Error exporting route: {e}")
        raise HTTPException(status_code=500, detail=f"Error exporting route: {str(e)}")
