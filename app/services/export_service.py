"""Route export service for GPX and GeoJSON formats."""

import io
import json
from datetime import datetime
from typing import Literal, Optional

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
            f"Difficulty: {route.difficulty.name.lower()}"
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
                for coords in segment.geometry:
                    lat, lon = coords[0], coords[1]
                    elev = coords[2] if len(coords) > 2 else (segment.start_node.elevation + segment.end_node.elevation) / 2
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
                for coords in segment.geometry:
                    lat, lon = coords[0], coords[1]
                    elev = coords[2] if len(coords) > 2 else (segment.start_node.elevation + segment.end_node.elevation) / 2
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
                "difficulty": route.difficulty.name.lower(),
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

    # ------------------------------------------------------------------
    # Map image export (contour + route overlay)
    # ------------------------------------------------------------------

    def export_to_map_image(
        self,
        route: Route,
        fmt: Literal["png", "pdf"] = "png",
        contour_interval: float = 10.0,
        bbox_padding_ratio_lat: float = 0.65,
        bbox_padding_ratio_lon: float = 0.40,
        min_padding_deg: float = 0.027,  # ~3 km
        nearby_nodes=None,  # List[Node] — extra peak/shelter/viewpoint nodes
    ) -> bytes:
        """
        Render a contour map with the route overlaid and return image bytes.

        Requires matplotlib, rasterio, numpy, and scipy.
        Falls back gracefully when DEM data is unavailable.
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.patheffects as pe
            import matplotlib.font_manager as fm
            import numpy as np

            # Register and apply Noto Sans TC for Chinese support
            _noto_path = "/Users/charlie/Library/Fonts/NotoSansTC-Regular.otf"
            try:
                fm.fontManager.addfont(_noto_path)
                plt.rcParams["font.family"] = fm.FontProperties(fname=_noto_path).get_name()
            except Exception:
                pass
            import rasterio
            from rasterio.windows import from_bounds
            from scipy.ndimage import gaussian_filter
        except ImportError as exc:
            raise RuntimeError(
                f"Map export requires matplotlib, rasterio, scipy: {exc}"
            ) from exc

        from app.config import settings

        logger.info(f"Exporting route {route.route_id} as contour map ({fmt})")

        # ── 1. Collect route coordinates ────────────────────────────────
        lats, lons = [], []
        for seg in route.segments:
            lats.append(seg.start_node.lat); lons.append(seg.start_node.lon)
            for pt in seg.geometry:
                lats.append(pt[0]); lons.append(pt[1])
        if route.segments:
            last = route.segments[-1]
            lats.append(last.end_node.lat); lons.append(last.end_node.lon)

        if not lats:
            raise ValueError("Route has no coordinates")

        # ── 2. Compute padded bbox ───────────────────────────────────────
        lat_min, lat_max = min(lats), max(lats)
        lon_min, lon_max = min(lons), max(lons)
        pad_lat = max((lat_max - lat_min) * bbox_padding_ratio_lat, min_padding_deg)
        pad_lon = max((lon_max - lon_min) * bbox_padding_ratio_lon, min_padding_deg)
        bbox = (
            lon_min - pad_lon,
            lat_min - pad_lat,
            lon_max + pad_lon,
            lat_max + pad_lat,
        )  # (west, south, east, north)

        # ── 3. Load DEM tile(s) for the bbox ────────────────────────────
        dem_array, dem_transform, dem_crs = self._read_dem_window(bbox, settings)

        # ── 4. Draw ──────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(14, 14), dpi=300)
        ax.set_aspect("equal")
        ax.set_facecolor("#f4f6f8")
        fig.patch.set_facecolor("#f4f6f8")

        if dem_array is not None:
            smooth = gaussian_filter(dem_array.astype(float), sigma=1.5)
            elev_min = np.nanmin(smooth)
            elev_max = np.nanmax(smooth)
            levels_major = np.arange(
                np.floor(elev_min / (contour_interval * 5)) * contour_interval * 5,
                np.ceil(elev_max / (contour_interval * 5)) * contour_interval * 5 + 1,
                contour_interval * 5,
            )
            levels_minor = np.arange(
                np.floor(elev_min / contour_interval) * contour_interval,
                np.ceil(elev_max / contour_interval) * contour_interval + 1,
                contour_interval,
            )

            # Build lon/lat grid matching raster pixels
            import rasterio.transform as rtransform
            nrows, ncols = smooth.shape
            xs = np.array([dem_transform.c + dem_transform.a * (j + 0.5) for j in range(ncols)])
            ys = np.array([dem_transform.f + dem_transform.e * (i + 0.5) for i in range(nrows)])

            # Convert to lon/lat if CRS is not EPSG:4326
            if dem_crs and not dem_crs.is_geographic:
                from pyproj import Transformer
                tr = Transformer.from_crs(dem_crs, "EPSG:4326", always_xy=True)
                xx, yy = np.meshgrid(xs, ys)
                lon_grid, lat_grid = tr.transform(xx, yy)
            else:
                lon_grid, lat_grid = np.meshgrid(xs, ys)

            # Hillshade for visual depth
            self._draw_hillshade(ax, smooth, lon_grid, lat_grid)

            # Minor contours — lighter so they read as background texture
            cs_minor = ax.contour(
                lon_grid, lat_grid, smooth,
                levels=levels_minor, colors="#90a0b0", linewidths=0.35, alpha=0.40,
            )
            # Major contours (every 5th) with labels
            cs_major = ax.contour(
                lon_grid, lat_grid, smooth,
                levels=levels_major, colors="#4a6070", linewidths=0.6, alpha=0.65,
            )
            clabels = ax.clabel(
                cs_major, fmt="%dm", fontsize=7, inline=True, inline_spacing=4,
            )
            # White halo behind contour labels so they lift off the lines
            for txt in clabels:
                txt.set_path_effects([
                    pe.withStroke(linewidth=3, foreground="white", alpha=0.9),
                    pe.Normal(),
                ])
        else:
            ax.text(
                0.5, 0.5, "DEM data not available for this area",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=12, color="#888",
            )

        # ── 5. Rivers ────────────────────────────────────────────────────
        self._draw_rivers(ax, bbox)

        # ── 6. Route line ────────────────────────────────────────────────
        ax.plot(
            lons, lats,
            color="#e63946", linewidth=2.2, zorder=5,
            solid_capstyle="round", solid_joinstyle="round",
            path_effects=[
                pe.Stroke(linewidth=4, foreground="white", alpha=0.6),
                pe.Normal(),
            ],
        )
        # Start / end markers
        ax.plot(lons[0], lats[0], "o", color="#2a9d8f", markersize=8,
                markeredgecolor="white", markeredgewidth=1.5, zorder=6)
        ax.plot(lons[-1], lats[-1], "s", color="#e76f51", markersize=8,
                markeredgecolor="white", markeredgewidth=1.5, zorder=6)

        # ── 6. Waypoint markers ──────────────────────────────────────────
        WAYPOINT_STYLE = {
            "peak":         ("^", "#d62828", 9),
            "shelter":      ("s", "#023e8a", 8),
            "hut":          ("s", "#023e8a", 8),
            "campsite":     ("P", "#386641", 8),
            "viewpoint":    ("*", "#f77f00", 10),
            "water_source": ("v", "#0077b6", 8),
            "trailhead":    ("D", "#7b2d8b", 8),
        }

        def _wp_fields(wp):
            """Normalise Node object or plain dict to (lat, lon, name, type, elev)."""
            if isinstance(wp, dict):
                return (
                    wp["lat"], wp["lon"],
                    wp.get("name") or wp.get("type", ""),
                    wp.get("type", ""),
                    wp.get("elevation"),
                )
            return (
                wp.lat, wp.lon,
                wp.name or wp.node_type.value,
                wp.node_type.value,
                wp.elevation,
            )

        def _draw_wp(wp, zorder, alpha=1.0):
            lat, lon, label, wtype, elev = _wp_fields(wp)
            marker, color, size = WAYPOINT_STYLE.get(wtype, ("o", "#555", 7))
            ax.plot(
                lon, lat, marker,
                color=color, markersize=size, alpha=alpha,
                markeredgecolor="white", markeredgewidth=1.2, zorder=zorder,
            )
            elev_str = f"\n{elev:.0f}m" if elev else ""
            ax.annotate(
                f"{label}{elev_str}",
                xy=(lon, lat),
                xytext=(5, 5), textcoords="offset points",
                fontsize=8, color="#111", alpha=alpha,
                zorder=zorder + 1,
                path_effects=[
                    pe.withStroke(linewidth=3.5, foreground="white", alpha=0.95),
                    pe.Normal(),
                ],
            )

        # Area points (all peaks/shelters/etc., slightly faded)
        route_wp_coords = {(_wp_fields(w)[0], _wp_fields(w)[1]) for w in route.waypoints}
        if nearby_nodes:
            for wp in nearby_nodes:
                _draw_wp(wp, zorder=6, alpha=0.75)

        # Route waypoints on top (full opacity), skip duplicates already drawn
        for wp in route.waypoints:
            _draw_wp(wp, zorder=7, alpha=1.0)

        # ── 7. Axes / title ──────────────────────────────────────────────
        ax.set_xlim(bbox[0], bbox[2])
        ax.set_ylim(bbox[1], bbox[3])
        ax.set_xlabel("Longitude", fontsize=10)
        ax.set_ylabel("Latitude", fontsize=10)
        ax.tick_params(labelsize=9)

        route_name = f"Route {route.route_id[:8]}"
        title_lines = [
            route_name,
            f"{route.total_distance:.1f} km  |  "
            f"↑{route.total_elevation_gain:.0f} m  |  "
            f"↓{route.total_elevation_loss:.0f} m  |  "
            f"{route.estimated_time:.1f} h  |  "
            f"{route.difficulty.name.capitalize()}",
        ]
        ax.set_title("\n".join(title_lines), fontsize=11, loc="left", pad=8)

        # Legend
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color="#e63946", lw=2, label="Route"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#2a9d8f",
                   markersize=7, label="Start"),
            Line2D([0], [0], marker="s", color="w", markerfacecolor="#e76f51",
                   markersize=7, label="End"),
        ] + [
            Line2D([0], [0], marker=m, color="w", markerfacecolor=c,
                   markersize=6, label=t.replace("_", " ").capitalize())
            for t, (m, c, _) in WAYPOINT_STYLE.items()
        ]
        ax.legend(
            handles=legend_elements, loc="lower right",
            fontsize=8, framealpha=0.85, ncol=2,
        )

        # ── Scale bar (bottom-left) ──────────────────────────────────────
        self._draw_scale_bar(ax, bbox)

        plt.tight_layout(pad=1.0)

        # ── 8. Serialise ─────────────────────────────────────────────────
        buf = io.BytesIO()
        if fmt == "pdf":
            fig.savefig(buf, format="pdf", bbox_inches="tight")
        else:
            fig.savefig(buf, format="png", bbox_inches="tight", dpi=300)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    # ------------------------------------------------------------------

    def _read_dem_window(self, bbox, settings):
        """
        Read DEM data for the given (west, south, east, north) bbox.
        Returns (array, transform, crs) or (None, None, None).
        """
        try:
            import rasterio
            from rasterio.errors import RasterioIOError
            from rasterio.windows import from_bounds
        except ImportError:
            return None, None, None

        west, south, east, north = bbox
        dem_dir = settings.local_dem_dir
        if not dem_dir.exists():
            return None, None, None

        for pattern in ("*.tif", "*.tiff", "*.TIF", "*.TIFF"):
            for dem_file in dem_dir.glob(pattern):
                try:
                    with rasterio.open(dem_file) as ds:
                        # Transform bbox to dataset CRS if needed
                        if not ds.crs.is_geographic:
                            from pyproj import Transformer
                            tr = Transformer.from_crs("EPSG:4326", ds.crs, always_xy=True)
                            x_min, y_min = tr.transform(west, south)
                            x_max, y_max = tr.transform(east, north)
                        else:
                            x_min, y_min, x_max, y_max = west, south, east, north

                        b = ds.bounds
                        # Check overlap
                        if x_max < b.left or x_min > b.right or y_max < b.bottom or y_min > b.top:
                            continue

                        win = from_bounds(
                            max(x_min, b.left), max(y_min, b.bottom),
                            min(x_max, b.right), min(y_max, b.top),
                            ds.transform,
                        )
                        arr = ds.read(1, window=win)
                        # Replace nodata
                        if ds.nodata is not None:
                            import numpy as np
                            arr = arr.astype(float)
                            arr[arr == ds.nodata] = np.nan
                        win_transform = ds.window_transform(win)
                        return arr, win_transform, ds.crs
                except Exception as e:
                    logger.debug(f"DEM read error for {dem_file}: {e}")
                    continue

        return None, None, None

    def _draw_hillshade(self, ax, dem, lon_grid, lat_grid):
        """Overlay a subtle hillshade for terrain depth."""
        try:
            import numpy as np
            from matplotlib.colors import LightSource

            ls = LightSource(azdeg=315, altdeg=45)
            # cell size in approximate metres (1° lat ≈ 111 km)
            dy = abs(lat_grid[1, 0] - lat_grid[0, 0]) * 111_000
            dx = abs(lon_grid[0, 1] - lon_grid[0, 0]) * 111_000 * np.cos(
                np.radians(np.nanmean(lat_grid))
            )
            shade = ls.hillshade(dem, dx=dx, dy=dy, vert_exag=2)
            ax.imshow(
                shade, cmap="gray", alpha=0.25, origin="upper",
                extent=[lon_grid.min(), lon_grid.max(), lat_grid.min(), lat_grid.max()],
                zorder=1,
            )
        except Exception:
            pass

    def _draw_rivers(self, ax, bbox):
        """Overlay river polygons clipped to bbox."""
        try:
            import geopandas as gpd
            from pathlib import Path

            shp = Path("data/river/riverpoly.shp")
            if not shp.exists():
                return

            west, south, east, north = bbox
            from pyproj import Transformer
            # Convert bbox to TWD97 (EPSG:3826) for spatial filter
            tr = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
            x_min, y_min = tr.transform(west, south)
            x_max, y_max = tr.transform(east, north)
            gdf = gpd.read_file(shp, bbox=(x_min, y_min, x_max, y_max))
            if gdf.empty:
                return

            gdf = gdf.set_crs("EPSG:3826").to_crs("EPSG:4326")

            gdf.plot(
                ax=ax,
                facecolor="#2c6fad",
                edgecolor="#2c6fad",
                linewidth=0.3,
                alpha=0.6,
                zorder=3,
            )
        except Exception as e:
            logger.debug(f"River overlay skipped: {e}")

    def _draw_scale_bar(self, ax, bbox):
        """Draw a simple scale bar in the bottom-left corner."""
        try:
            import numpy as np

            west, south, east, north = bbox
            lat_mid = (south + north) / 2

            # Pick a round target distance (km), find nearest nice value
            map_width_km = (east - west) * 111.0 * np.cos(np.radians(lat_mid))
            target_km = map_width_km / 5
            for nice in [0.5, 1, 2, 5, 10, 20, 50]:
                if nice >= target_km * 0.4:
                    bar_km = nice
                    break
            else:
                bar_km = round(target_km)

            # Convert km → degrees longitude
            bar_deg = bar_km / (111.0 * np.cos(np.radians(lat_mid)))

            # Position: 3% from left/bottom in data coords
            x0 = west + (east - west) * 0.03
            y0 = south + (north - south) * 0.04
            x1 = x0 + bar_deg

            # Draw bar
            ax.plot([x0, x1], [y0, y0], color="#222", linewidth=3,
                    solid_capstyle="butt", zorder=10)
            ax.plot([x0, x0], [y0 - (north - south) * 0.005,
                                y0 + (north - south) * 0.005],
                    color="#222", linewidth=2, zorder=10)
            ax.plot([x1, x1], [y0 - (north - south) * 0.005,
                                y0 + (north - south) * 0.005],
                    color="#222", linewidth=2, zorder=10)

            label = f"{bar_km:.0f} km" if bar_km >= 1 else f"{bar_km*1000:.0f} m"
            import matplotlib.patheffects as _pe
            ax.text(
                (x0 + x1) / 2, y0 + (north - south) * 0.012, label,
                ha="center", va="bottom", fontsize=8, color="#222", zorder=11,
                path_effects=[
                    _pe.withStroke(linewidth=3, foreground="white", alpha=0.9),
                    _pe.Normal(),
                ],
            )
        except Exception:
            pass
