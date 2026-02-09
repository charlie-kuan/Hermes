"""Caching utilities for graphs and routes."""

import hashlib
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from app.config import settings


class CacheManager:
    """Manages caching for graphs and routes."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str, extension: str = "pkl") -> Path:
        """Get cache file path for a given key."""
        return self.cache_dir / f"{key}.{extension}"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid based on expiry time."""
        if not cache_path.exists():
            return False

        if not settings.enable_graph_cache:
            return False

        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expiry = timedelta(hours=settings.cache_expiry_hours)

        return datetime.now() - mtime < expiry

    def save_graph(self, key: str, graph: Any) -> None:
        """
        Save a NetworkX graph to cache.

        Args:
            key: Cache key (usually area_id)
            graph: NetworkX graph to cache
        """
        cache_path = self._get_cache_path(key, "pkl")
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(graph, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info(f"Cached graph for key: {key}")
        except Exception as e:
            logger.error(f"Failed to cache graph for {key}: {e}")

    def load_graph(self, key: str) -> Optional[Any]:
        """
        Load a NetworkX graph from cache.

        Args:
            key: Cache key (usually area_id)

        Returns:
            Cached graph or None if not found/expired
        """
        cache_path = self._get_cache_path(key, "pkl")

        if not self._is_cache_valid(cache_path):
            logger.debug(f"Cache miss or expired for key: {key}")
            return None

        try:
            with open(cache_path, 'rb') as f:
                graph = pickle.load(f)
            logger.info(f"Loaded graph from cache for key: {key}")
            return graph
        except Exception as e:
            logger.error(f"Failed to load cached graph for {key}: {e}")
            return None

    def clear_cache(self, key: Optional[str] = None) -> None:
        """
        Clear cache for a specific key or all cache.

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key:
            cache_path = self._get_cache_path(key, "pkl")
            if cache_path.exists():
                cache_path.unlink()
                logger.info(f"Cleared cache for key: {key}")
        else:
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            logger.info("Cleared all cache")

    def generate_route_key(self, **params) -> str:
        """
        Generate a unique cache key for route parameters.

        Args:
            **params: Route parameters to hash

        Returns:
            Unique cache key
        """
        # Sort params for consistent hashing
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.sha256(param_str.encode()).hexdigest()[:16]


# Global cache manager instances
graph_cache = CacheManager(settings.graph_cache_dir)
