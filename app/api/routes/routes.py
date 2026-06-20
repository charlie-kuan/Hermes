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
    DayPlanResponse,
    EquipmentRecommendationResponse,
    FoodRecommendationResponse,
    LegResponse,
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


def _resolve_node_with_distance(
    graph_service: GraphService,
    graph,
    lat: float,
    lon: float,
    nearest_max_distance: float = 2000.0,
    edge_snap_max_distance: float = 3000.0
) -> tuple[Optional[str], float]:
    """Resolve a coordinate and return (node_id, snap_distance_metres)."""
    node_id, dist = graph_service.find_nearest_node_with_distance(
        graph, lat, lon, max_distance=nearest_max_distance
    )
    if node_id:
        return node_id, dist

    node_id = graph_service.find_or_create_node_at_point(
        graph,
        lat,
        lon,
        max_distance=edge_snap_max_distance,
        split_edges=True
    )
    return node_id, dist  # dist here is the nearest-node dist (proxy for how far we snapped)


_GRAPH_EXPANSION_SNAP_THRESHOLD_M = 300.0


def _expand_bbox_for_coords(
    area_data: Optional[dict],
    extra_coords: list[tuple[float, float]],
    buffer_km: float = 2.0
) -> list[float]:
    """Build a bbox covering area_data routes + any extra coordinates."""
    from app.utils.geo_utils import calculate_bbox_from_area_data

    lats = [lat for lat, _ in extra_coords]
    lons = [lon for _, lon in extra_coords]

    if area_data:
        try:
            base = calculate_bbox_from_area_data(area_data, buffer_km=buffer_km)
            # Union with extra coords
            lats += [base[0], base[2]]
            lons += [base[1], base[3]]
        except ValueError:
            pass

    buffer_deg = buffer_km / 111.0
    return [
        min(lats) - buffer_deg,
        min(lons) - buffer_deg,
        max(lats) + buffer_deg,
        max(lons) + buffer_deg,
    ]


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



def _build_legs(segments: list, split_node_ids: list, name_by_node_id: dict = None) -> list:
    """Aggregate segments into user-defined legs (start→via1→via2→end)."""
    if not split_node_ids:
        return []
    name_by_node_id = name_by_node_id or {}
    split_set = set(split_node_ids)
    legs = []
    current = []
    seg_start = 0

    def _named(node):
        r = node_to_response(node)
        if node.id in name_by_node_id:
            r.name = name_by_node_id[node.id]
        return r

    for idx, seg in enumerate(segments):
        current.append(seg)
        if seg.end_node.id in split_set or seg is segments[-1]:
            dist = sum(s.distance for s in current)
            gain = sum(s.elevation_gain for s in current)
            loss = sum(s.elevation_loss for s in current)
            time = sum(s.estimated_time for s in current)
            legs.append(LegResponse(
                start_node=_named(current[0].start_node),
                end_node=_named(current[-1].end_node),
                distance=dist,
                elevation_gain=gain,
                elevation_loss=loss,
                estimated_time=time,
                segment_start=seg_start,
                segment_end=idx,
            ))
            seg_start = idx + 1
            current = []
    return legs


def _build_day_plans(
    segments: list,
    overnight_node_ids: list,
    estimation_service,
    hiker_fitness: str,
    pack_weight_kg: float,
    night_by_node_id: dict = None,
    name_override_by_node_id: dict = None,
) -> list:
    """Split route segments into per-day plans based on overnight stop node IDs."""
    if not overnight_node_ids:
        return []

    # Use an ordered queue so each overnight stop is consumed exactly once,
    # preventing duplicate day-breaks when the route passes the same node twice
    # (e.g. a lodge visited on the way up and again on the way back).
    remaining_stops = list(overnight_node_ids)
    night_by_node_id = night_by_node_id or {}
    name_override_by_node_id = name_override_by_node_id or {}
    days = []
    current_segs = []
    day_num = 1

    for seg in segments:
        current_segs.append(seg)
        next_stop = remaining_stops[0] if remaining_stops else None
        is_stop = next_stop is not None and seg.end_node.id == next_stop
        if is_stop:
            remaining_stops.pop(0)
        if is_stop or seg is segments[-1]:
            stop_node = seg.end_node if is_stop else None
            dist = sum(s.distance for s in current_segs)
            gain = sum(s.elevation_gain for s in current_segs)
            loss = sum(s.elevation_loss for s in current_segs)

            from app.models.domain import Route as DomainRoute
            dummy_route = DomainRoute(
                route_id="",
                segments=current_segs,
                total_distance=dist,
                total_elevation_gain=gain,
                total_elevation_loss=loss,
                estimated_time=0.0,
                difficulty=max(s.difficulty for s in current_segs),
                waypoints=[],
            )
            opt, norm, cons = estimation_service.estimate_route(dummy_route, hiker_fitness, pack_weight_kg)

            if stop_node and not stop_node.name and stop_node.id in name_override_by_node_id:
                stop_node.name = name_override_by_node_id[stop_node.id]
            days.append(DayPlanResponse(
                day=day_num,
                overnight_stop=node_to_response(stop_node) if stop_node else None,
                segments=[segment_to_response(s) for s in current_segs],
                distance=dist,
                elevation_gain=gain,
                elevation_loss=loss,
                estimated_time=TimeEstimate(optimistic=opt, normal=norm, conservative=cons),
            ))
            day_num += 1
            current_segs = []

    return days


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

        def _resolve_all_nodes(g):
            """Resolve start, end, via, overnight nodes against graph g.
            Returns a dict with all resolved IDs and snap distances."""
            s_id, s_snap = _resolve_node_with_distance(
                graph_service, g, request.start_lat, request.start_lon,
            )

            e_id, e_snap = None, 0.0
            if not request.loop_route and request.end_lat and request.end_lon:
                e_id, e_snap = _resolve_node_with_distance(
                    graph_service, g, request.end_lat, request.end_lon,
                )

            via_raw = []  # [(node_id, snap_m, lat, lon, name)]
            if request.via_points:
                for vp in request.via_points:
                    v_lat, v_lon = vp.get('lat'), vp.get('lon')
                    if v_lat and v_lon:
                        v_id, v_snap = _resolve_node_with_distance(
                            graph_service, g, v_lat, v_lon,
                        )
                        via_raw.append((v_id, v_snap, v_lat, v_lon, vp.get('name')))

            ons = []  # overnight stops — snap distance not critical
            n_by_id: dict = {}
            name_ov: dict = {}
            if request.overnight_stops:
                for stop in request.overnight_stops:
                    s_lat2, s_lon2 = stop.get('lat'), stop.get('lon')
                    if s_lat2 and s_lon2:
                        nid = graph_service.find_nearest_node(g, s_lat2, s_lon2)
                        if nid:
                            ons.append(nid)
                            if stop.get('night'):
                                n_by_id[nid] = stop['night']
                            if stop.get('name'):
                                name_ov[nid] = stop['name']

            return {
                'start_id': s_id, 'start_snap': s_snap,
                'end_id': e_id, 'end_snap': e_snap,
                'via_raw': via_raw,
                'overnight_ids': ons,
                'night_by_node_id': n_by_id,
                'name_override_by_node_id': name_ov,
            }

        # ── Phase 1: resolve everything against the current (possibly cached) graph ──
        resolved = _resolve_all_nodes(graph)

        # ── Phase 2: detect coverage gaps and rebuild if needed ──────────────
        #
        # A snap distance > threshold means the cached graph's bbox didn't reach
        # that coordinate.  Collect all such coordinates and rebuild once with an
        # expanded bbox that explicitly covers them.
        out_of_coverage: list[tuple[float, float]] = []

        if not resolved['start_id'] or resolved['start_snap'] > _GRAPH_EXPANSION_SNAP_THRESHOLD_M:
            out_of_coverage.append((request.start_lat, request.start_lon))

        if not request.loop_route and request.end_lat and request.end_lon:
            if not resolved['end_id'] or resolved['end_snap'] > _GRAPH_EXPANSION_SNAP_THRESHOLD_M:
                out_of_coverage.append((request.end_lat, request.end_lon))

        for v_id, v_snap, v_lat, v_lon, _ in resolved['via_raw']:
            if not v_id or v_snap > _GRAPH_EXPANSION_SNAP_THRESHOLD_M:
                out_of_coverage.append((v_lat, v_lon))

        if out_of_coverage:
            snap_info = (
                f"start={resolved['start_snap']:.0f}m, "
                f"end={resolved['end_snap']:.0f}m, "
                f"via=[{', '.join(f'{s:.0f}m' for _, s, *_ in resolved['via_raw'])}]"
            )
            logger.warning(
                f"Graph coverage gap for {request.area_id} ({snap_info}). "
                f"Rebuilding with expanded bbox covering {out_of_coverage}."
            )
            expanded_bbox = _expand_bbox_for_coords(area_data, out_of_coverage, buffer_km=2.0)
            graph_service.clear_cache(request.area_id)
            graph = graph_service.get_or_build_graph(
                request.area_id,
                bbox=expanded_bbox,
                area_data=area_data,
            )
            resolved = _resolve_all_nodes(graph)

        # ── Phase 3: hard failure if still unresolved ────────────────────────
        if not resolved['start_id']:
            raise HTTPException(
                status_code=400,
                detail=f"No trail found near start ({request.start_lat:.5f}, {request.start_lon:.5f}) "
                       f"even after graph rebuild."
            )
        if not request.loop_route and request.end_lat and request.end_lon and not resolved['end_id']:
            raise HTTPException(
                status_code=400,
                detail=f"No trail found near end ({request.end_lat:.5f}, {request.end_lon:.5f}) "
                       f"even after graph rebuild."
            )

        start_node_id = resolved['start_id']
        end_node_id = resolved['end_id']
        overnight_node_ids = resolved['overnight_ids']
        night_by_node_id = resolved['night_by_node_id']
        name_override_by_node_id = resolved['name_override_by_node_id']

        # Build name map for user-selected points (to override "intersection" labels)
        name_by_node_id = {}
        if request.start_name and start_node_id:
            name_by_node_id[start_node_id] = request.start_name
        if request.end_name and end_node_id:
            name_by_node_id[end_node_id] = request.end_name

        # Convert via points to node IDs (already resolved; collect names)
        via_node_ids = None
        if resolved['via_raw']:
            via_node_ids = []
            for v_id, _, _, _, v_name in resolved['via_raw']:
                if v_id:
                    via_node_ids.append(v_id)
                    if v_name:
                        name_by_node_id[v_id] = v_name

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

        # Build legs between user-selected points (via + end)
        leg_split_ids = (via_node_ids or []) + ([end_node_id] if end_node_id else [start_node_id])
        legs = _build_legs(route.segments, leg_split_ids, name_by_node_id=name_by_node_id)

        # Build day plans if overnight stops were provided
        day_plans = _build_day_plans(
            route.segments,
            overnight_node_ids,
            estimation_service,
            request.hiker_fitness,
            request.pack_weight_kg or 12.0,
            night_by_node_id=night_by_node_id,
            name_override_by_node_id=name_override_by_node_id,
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
            legs=legs,
            day_plans=day_plans,
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
