"""Route planning endpoint handlers."""

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from loguru import logger

from app.api.dependencies import (
    get_estimation_service,
    get_export_service,
    get_graph_service,
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
    EquipmentRecommendation,
    FoodRecommendation,
    Node,
    Route,
    RouteSegment
)
from app.models.requests import RoutePlanRequest, TimeEstimateRequest
from app.models.responses import (
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
from app.services.recommendation_service import RecommendationService
from app.services.routing_service import RoutingService

router = APIRouter()

# In-memory route cache (in production, use Redis or similar)
route_cache: Dict[str, Route] = {}


def _resolve_node_id(
    graph_service: GraphService,
    graph,
    lat: float,
    lon: float,
    nearest_max_distance: float = 2000.0,
    edge_snap_max_distance: float = 3000.0
) -> Optional[str]:
    """Resolve a coordinate to an existing node or by edge snapping."""
    node_id = graph_service.find_nearest_node(
        graph, lat, lon, max_distance=nearest_max_distance
    )
    if node_id:
        return node_id

    return graph_service.find_or_create_node_at_point(
        graph,
        lat,
        lon,
        max_distance=edge_snap_max_distance,
        split_edges=True
    )


def _build_retry_bbox(
    start_lat: float,
    start_lon: float,
    end_lat: Optional[float],
    end_lon: Optional[float],
    padding_km: float = 6.0
) -> list[float]:
    """Build a small bbox around query points for rebuild fallback."""
    lats = [start_lat]
    lons = [start_lon]

    if end_lat is not None and end_lon is not None:
        lats.append(end_lat)
        lons.append(end_lon)

    padding_deg = padding_km / 111.0
    return [
        min(lats) - padding_deg,
        min(lons) - padding_deg,
        max(lats) + padding_deg,
        max(lons) + padding_deg
    ]


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
    # Include geometry with elevation (3-element lists) when available,
    # fall back to 2-element [lat, lon] for points without elevation data.
    geometry = [
        [pt[0], pt[1], pt[2]] if len(pt) >= 3 else [pt[0], pt[1]]
        for pt in (segment.geometry or [])
    ]
    return RouteSegmentResponse(
        start_node=node_to_response(segment.start_node),
        end_node=node_to_response(segment.end_node),
        distance=segment.distance,
        elevation_gain=segment.elevation_gain,
        elevation_loss=segment.elevation_loss,
        estimated_time=segment.estimated_time,
        difficulty=segment.difficulty.name.lower(),
        trail_name=segment.edge.trail_name,
        geometry=geometry
    )



@router.post("/routes/plan", response_model=RouteResponse, tags=["Routes"])
async def plan_route(
    request: RoutePlanRequest,
    graph_service: GraphService = Depends(get_graph_service),
    routing_service: RoutingService = Depends(get_routing_service),
    estimation_service: EstimationService = Depends(get_estimation_service),
    recommendation_service: RecommendationService = Depends(get_recommendation_service)
):
    """
    Plan a hiking route.

    Creates a complete route plan with time estimates and equipment/food recommendations.

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
        start_node_id = _resolve_node_id(
            graph_service,
            graph,
            request.start_lat,
            request.start_lon,
            nearest_max_distance=2000.0,
            edge_snap_max_distance=3000.0
        )

        # Retry path: stale/too-small cached graph can miss nearby trails
        if not start_node_id:
            logger.warning(
                f"Start node not found for {request.area_id}; rebuilding graph with expanded query bbox"
            )
            retry_bbox = _build_retry_bbox(
                request.start_lat,
                request.start_lon,
                request.end_lat,
                request.end_lon,
                padding_km=6.0
            )

            graph_service.clear_cache(request.area_id)
            graph = graph_service.get_or_build_graph(
                request.area_id,
                bbox=retry_bbox,
                area_data=area_data
            )

            start_node_id = _resolve_node_id(
                graph_service,
                graph,
                request.start_lat,
                request.start_lon,
                nearest_max_distance=5000.0,
                edge_snap_max_distance=5000.0
            )

        if not start_node_id:
            raise HTTPException(
                status_code=400,
                  detail=f"No trail found within 2km of start coordinates ({request.start_lat:.5f}, {request.start_lon:.5f}) "
                      f"(including 3km edge-snap fallback and 5km retry after graph rebuild). "
                       f"Please select a location closer to the trail network."
            )

        # Find end node (if not loop)
        end_node_id = None
        if not request.loop_route and request.end_lat and request.end_lon:
            end_node_id = _resolve_node_id(
                graph_service,
                graph,
                request.end_lat,
                request.end_lon,
                nearest_max_distance=2000.0,
                edge_snap_max_distance=3000.0
            )

            if not end_node_id:
                end_node_id = _resolve_node_id(
                    graph_service,
                    graph,
                    request.end_lat,
                    request.end_lon,
                    nearest_max_distance=5000.0,
                    edge_snap_max_distance=5000.0
                )

            if not end_node_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"No trail found within 2km of end coordinates ({request.end_lat:.5f}, {request.end_lon:.5f}) "
                              f"(including 3km edge-snap fallback and 5km retry after graph rebuild). "
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

        # Plan the route
        route = routing_service.plan_route(
            graph,
            start_node_id,
            end_node_id,
            via_nodes=via_node_ids,
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

        # Generate recommendations
        equipment = recommendation_service.recommend_equipment(route)

        food = recommendation_service.recommend_food(
            route, request.hiker_fitness, request.pack_weight_kg
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

    # Get time estimates
    optimistic, normal, conservative = estimation_service.estimate_route(route)

    time_estimate = TimeEstimate(
        optimistic=optimistic,
        normal=normal,
        conservative=conservative
    )

    return RouteResponse(
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
    )


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
