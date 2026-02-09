"""Elevation data processing using SRTM."""

from typing import Dict, List, Optional

import numpy as np
from loguru import logger

try:
    import srtm
    SRTM_AVAILABLE = True
except ImportError:
    logger.warning("srtm.py not available, elevation data will be limited to OSM tags")
    SRTM_AVAILABLE = False

from app.exceptions import ElevationDataError


class ElevationProcessor:
    """Handles elevation data retrieval and processing."""

    def __init__(self):
        if SRTM_AVAILABLE:
            self.elevation_data = srtm.get_data()
        else:
            self.elevation_data = None

    def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        """
        Get elevation for a specific point using SRTM data.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Elevation in meters or None if unavailable
        """
        if not SRTM_AVAILABLE or self.elevation_data is None:
            return None

        try:
            elevation = self.elevation_data.get_elevation(lat, lon)
            return float(elevation) if elevation is not None else None
        except Exception as e:
            logger.debug(f"Failed to get elevation for ({lat}, {lon}): {e}")
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
