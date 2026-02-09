"""Route export service for GPX and GeoJSON formats."""

import json
from datetime import datetime
from typing import Optional

import gpxpy
import gpxpy.gpx
from loguru import logger

from app.models.domain import Node, Route, RouteSegment


class ExportService:
    """Handles exporting routes to various formats."""

    def __init__(self):
        pass

    def export_to_gpx(self, route: Route, route_name: Optional[str] = None) -> str:
        """
        Export route to GPX format.

        Args:
            route: Route to export
            route_name: Optional route name

        Returns:
            GPX file content as string
        """
        logger.info(f"Exporting route {route.route_id} to GPX")

        # Create GPX object
        gpx = gpxpy.gpx.GPX()

        # Metadata
        gpx.name = route_name or f"Route {route.route_id[:8]}"
        gpx.description = (
            f"Distance: {route.total_distance:.1f} km, "
            f"Elevation Gain: {route.total_elevation_gain:.0f} m, "
            f"Estimated Time: {route.estimated_time:.1f} hours, "
            f"Difficulty: {route.difficulty.value}"
        )
        gpx.author_name = "Project Hermes"
        gpx.time = datetime.utcnow()

        # Create track
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_track.name = gpx.name
        gpx_track.description = gpx.description
        gpx.tracks.append(gpx_track)

        # Create track segment
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        # Add points from route segments
        for segment in route.segments:
            # Add start node
            point = gpxpy.gpx.GPXTrackPoint(
                latitude=segment.start_node.lat,
                longitude=segment.start_node.lon,
                elevation=segment.start_node.elevation,
                time=datetime.utcnow()
            )
            gpx_segment.points.append(point)

            # Add intermediate geometry points if available
            if segment.geometry:
                for lat, lon in segment.geometry:
                    # Interpolate elevation (simplified)
                    elev = (segment.start_node.elevation + segment.end_node.elevation) / 2
                    point = gpxpy.gpx.GPXTrackPoint(
                        latitude=lat,
                        longitude=lon,
                        elevation=elev
                    )
                    gpx_segment.points.append(point)

        # Add final endpoint
        if route.segments:
            last_segment = route.segments[-1]
            point = gpxpy.gpx.GPXTrackPoint(
                latitude=last_segment.end_node.lat,
                longitude=last_segment.end_node.lon,
                elevation=last_segment.end_node.elevation,
                time=datetime.utcnow()
            )
            gpx_segment.points.append(point)

        # Add waypoints for peaks, huts, etc.
        for waypoint in route.waypoints:
            gpx_waypoint = gpxpy.gpx.GPXWaypoint(
                latitude=waypoint.lat,
                longitude=waypoint.lon,
                elevation=waypoint.elevation,
                name=waypoint.name or waypoint.node_type.value,
                description=f"{waypoint.node_type.value} - {', '.join(waypoint.amenities)}" if waypoint.amenities else waypoint.node_type.value,
                type=waypoint.node_type.value
            )
            gpx.waypoints.append(gpx_waypoint)

        return gpx.to_xml()

    def export_to_geojson(self, route: Route, route_name: Optional[str] = None) -> str:
        """
        Export route to GeoJSON format.

        Args:
            route: Route to export
            route_name: Optional route name

        Returns:
            GeoJSON content as string
        """
        logger.info(f"Exporting route {route.route_id} to GeoJSON")

        features = []

        # Create LineString for route path
        coordinates = []

        for segment in route.segments:
            # Add start point
            coordinates.append([
                segment.start_node.lon,
                segment.start_node.lat,
                segment.start_node.elevation
            ])

            # Add intermediate geometry points
            if segment.geometry:
                for lat, lon in segment.geometry:
                    elev = (segment.start_node.elevation + segment.end_node.elevation) / 2
                    coordinates.append([lon, lat, elev])

        # Add final endpoint
        if route.segments:
            last_segment = route.segments[-1]
            coordinates.append([
                last_segment.end_node.lon,
                last_segment.end_node.lat,
                last_segment.end_node.elevation
            ])

        # Route LineString feature
        route_feature = {
            "type": "Feature",
            "properties": {
                "name": route_name or f"Route {route.route_id[:8]}",
                "distance_km": round(route.total_distance, 2),
                "elevation_gain_m": round(route.total_elevation_gain, 0),
                "elevation_loss_m": round(route.total_elevation_loss, 0),
                "estimated_time_hours": round(route.estimated_time, 1),
                "difficulty": route.difficulty.value,
                "is_loop": route.is_loop,
                "stroke": "#FF5733",
                "stroke-width": 3
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            }
        }
        features.append(route_feature)

        # Add waypoint features
        for waypoint in route.waypoints:
            waypoint_feature = {
                "type": "Feature",
                "properties": {
                    "name": waypoint.name or waypoint.node_type.value,
                    "type": waypoint.node_type.value,
                    "elevation_m": round(waypoint.elevation, 0),
                    "amenities": waypoint.amenities,
                    "marker-color": self._get_marker_color(waypoint),
                    "marker-symbol": self._get_marker_symbol(waypoint)
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [waypoint.lon, waypoint.lat, waypoint.elevation]
                }
            }
            features.append(waypoint_feature)

        # Create FeatureCollection
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        return json.dumps(geojson, indent=2)

    def _get_marker_color(self, node: Node) -> str:
        """Get marker color based on node type."""
        colors = {
            "peak": "#FF0000",
            "hut": "#0000FF",
            "campsite": "#00FF00",
            "viewpoint": "#FFA500",
            "water_source": "#00FFFF",
            "trailhead": "#800080"
        }
        return colors.get(node.node_type.value, "#808080")

    def _get_marker_symbol(self, node: Node) -> str:
        """Get marker symbol based on node type."""
        symbols = {
            "peak": "triangle",
            "hut": "lodging",
            "campsite": "campsite",
            "viewpoint": "camera",
            "water_source": "water",
            "trailhead": "entrance"
        }
        return symbols.get(node.node_type.value, "marker")
