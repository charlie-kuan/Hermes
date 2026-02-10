"""Elevation data processing using local DEM and SRTM."""

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from loguru import logger

try:
    import rasterio
    from rasterio.errors import RasterioIOError
    RASTERIO_AVAILABLE = True
except ImportError:
    logger.warning("rasterio not available, local DEM support disabled")
    RASTERIO_AVAILABLE = False
    RasterioIOError = Exception

try:
    import srtm
    SRTM_AVAILABLE = True
except ImportError:
    logger.warning("srtm.py not available, elevation data will be limited to OSM tags")
    SRTM_AVAILABLE = False

from app.config import settings
from app.exceptions import ElevationDataError


class ElevationProcessor:
    """Handles elevation data retrieval and processing."""

    def __init__(self):
        # Local DEM files
        self.dem_files = []
        self.dem_datasets = []  # Keep datasets open for performance
        
        if settings.use_local_dem and RASTERIO_AVAILABLE:
            self._load_local_dem_files()
        
        # SRTM fallback
        if SRTM_AVAILABLE:
            self.elevation_data = srtm.get_data()
        else:
            self.elevation_data = None
    
    def _load_local_dem_files(self):
        """Load local DEM files (GeoTIFF) from the DEM directory."""
        dem_dir = settings.local_dem_dir
        if not dem_dir.exists():
            logger.info(f"Local DEM directory not found: {dem_dir}")
            return
        
        # Find all GeoTIFF files
        dem_patterns = ['*.tif', '*.tiff', '*.TIF', '*.TIFF']
        for pattern in dem_patterns:
            for dem_file in dem_dir.glob(pattern):
                try:
                    dataset = rasterio.open(dem_file)
                    self.dem_datasets.append(dataset)
                    self.dem_files.append(dem_file)
                    logger.info(f"Loaded DEM file: {dem_file.name} (bounds: {dataset.bounds})")
                except Exception as e:
                    logger.warning(f"Failed to load DEM file {dem_file}: {e}")
        
        if self.dem_datasets:
            logger.info(f"Loaded {len(self.dem_datasets)} local DEM file(s)")
        else:
            logger.warning(f"No DEM files found in {dem_dir}. Place GeoTIFF files there for faster elevation queries.")
    
    def __del__(self):
        """Close DEM datasets on cleanup."""
        for dataset in self.dem_datasets:
            try:
                dataset.close()
            except:
                pass

    def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        """
        Get elevation for a specific point. Tries local DEM first, then SRTM.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Elevation in meters or None if unavailable
        """
        # Try local DEM first (much faster!)
        if self.dem_datasets:
            elev = self._get_elevation_from_local_dem(lat, lon)
            if elev is not None:
                return elev
        
        # Fallback to SRTM (requires download)
        if SRTM_AVAILABLE and self.elevation_data is not None:
            try:
                elevation = self.elevation_data.get_elevation(lat, lon)
                return float(elevation) if elevation is not None else None
            except Exception as e:
                logger.debug(f"Failed to get elevation from SRTM for ({lat}, {lon}): {e}")
        
        return None
    
    def _get_elevation_from_local_dem(self, lat: float, lon: float) -> Optional[float]:
        """
        Get elevation from local DEM files.
        
        Args:
            lat: Latitude (WGS84)
            lon: Longitude (WGS84)
            
        Returns:
            Elevation in meters or None if not in any DEM coverage
        """
        for dataset in self.dem_datasets:
            try:
                # Get DEM's coordinate reference system
                dem_crs = dataset.crs
                
                # If DEM is not in WGS84, transform coordinates
                if dem_crs and dem_crs.to_epsg() != 4326:
                    try:
                        from pyproj import Transformer
                        # Create transformer from WGS84 to DEM's CRS
                        transformer = Transformer.from_crs("EPSG:4326", dem_crs, always_xy=True)
                        x, y = transformer.transform(lon, lat)
                    except Exception as e:
                        logger.debug(f"Coordinate transformation failed: {e}")
                        continue
                else:
                    # DEM is in WGS84, use directly
                    x, y = lon, lat
                
                # Check if point is within bounds
                bounds = dataset.bounds
                if not (bounds.left <= x <= bounds.right and 
                       bounds.bottom <= y <= bounds.top):
                    continue
                
                # Convert to pixel coordinates
                row, col = dataset.index(x, y)
                
                # Read elevation value
                window = ((row, row + 1), (col, col + 1))
                data = dataset.read(1, window=window)
                
                if data.size > 0:
                    elevation = float(data[0, 0])
                    # Check for nodata values
                    if dataset.nodata is not None and elevation == dataset.nodata:
                        continue
                    return elevation
                    
            except (IndexError, RasterioIOError) as e:
                # Point outside this DEM's coverage
                continue
            except Exception as e:
                logger.debug(f"Error reading DEM at ({lat}, {lon}): {e}")
                continue
        
        return None

    def get_elevations_batch(self, coordinates: List[tuple]) -> Dict[tuple, Optional[float]]:
        """
        Get elevations for multiple points.

        Args:
            coordinates: List of (lat, lon) tuples

        Returns:
            Dictionary mapping (lat, lon) to elevation
        """
        results = {}
        for lat, lon in coordinates:
            results[(lat, lon)] = self.get_elevation(lat, lon)
        return results

    def calculate_elevation_gain_loss(
        self,
        elevations: List[float]
    ) -> tuple[float, float]:
        """
        Calculate total elevation gain and loss from a sequence of elevations.

        Args:
            elevations: List of elevation values in order

        Returns:
            Tuple of (total_gain, total_loss) in meters
        """
        if len(elevations) < 2:
            return 0.0, 0.0

        gain = 0.0
        loss = 0.0

        for i in range(1, len(elevations)):
            diff = elevations[i] - elevations[i - 1]
            if diff > 0:
                gain += diff
            else:
                loss += abs(diff)

        return gain, loss

    def smooth_elevation_profile(
        self,
        elevations: List[float],
        window_size: int = 3
    ) -> List[float]:
        """
        Smooth elevation profile using moving average to remove noise.

        Args:
            elevations: Raw elevation data
            window_size: Window size for moving average (must be odd)

        Returns:
            Smoothed elevation profile
        """
        if len(elevations) < window_size:
            return elevations

        # Ensure window size is odd
        if window_size % 2 == 0:
            window_size += 1

        smoothed = []
        half_window = window_size // 2

        for i in range(len(elevations)):
            start = max(0, i - half_window)
            end = min(len(elevations), i + half_window + 1)
            window = elevations[start:end]
            smoothed.append(np.mean(window))

        return smoothed

    def interpolate_missing_elevations(
        self,
        elevations: List[Optional[float]]
    ) -> List[float]:
        """
        Interpolate missing elevation values.

        Args:
            elevations: List of elevations with possible None values

        Returns:
            List with interpolated values
        """
        result = []
        last_valid = None
        last_valid_idx = -1

        # First pass: forward fill
        for i, elev in enumerate(elevations):
            if elev is not None:
                result.append(float(elev))
                last_valid = float(elev)
                last_valid_idx = i
            elif last_valid is not None:
                result.append(last_valid)
            else:
                result.append(0.0)  # Default if no valid value yet

        # Second pass: linear interpolation
        for i in range(len(result)):
            if elevations[i] is None and last_valid_idx >= 0:
                # Find next valid value
                next_valid_idx = None
                for j in range(i + 1, len(elevations)):
                    if elevations[j] is not None:
                        next_valid_idx = j
                        break

                if next_valid_idx is not None:
                    # Linear interpolation
                    prev_elev = result[last_valid_idx]
                    next_elev = elevations[next_valid_idx]
                    ratio = (i - last_valid_idx) / (next_valid_idx - last_valid_idx)
                    result[i] = prev_elev + ratio * (next_elev - prev_elev)

        return result
