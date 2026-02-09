"""Application configuration management using Pydantic Settings."""

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = Field(default="Project Hermes", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Data Directories
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    osm_cache_dir: Path = Field(default=Path("./data/osm"), alias="OSM_CACHE_DIR")
    elevation_cache_dir: Path = Field(default=Path("./data/elevation"), alias="ELEVATION_CACHE_DIR")
    graph_cache_dir: Path = Field(default=Path("./data/graphs"), alias="GRAPH_CACHE_DIR")

    # Routing Configuration
    default_fitness_level: str = Field(default="moderate", alias="DEFAULT_FITNESS_LEVEL")
    default_pack_weight_kg: float = Field(default=12.0, alias="DEFAULT_PACK_WEIGHT_KG")
    default_hours_per_day: float = Field(default=7.0, alias="DEFAULT_HOURS_PER_DAY")
    max_route_distance_km: float = Field(default=100.0, alias="MAX_ROUTE_DISTANCE_KM")

    # OSM Configuration
    osm_user_agent: str = Field(default="project_hermes_hiking_planner", alias="OSM_USER_AGENT")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        alias="CORS_ORIGINS"
    )

    # Cache Configuration
    enable_graph_cache: bool = Field(default=True, alias="ENABLE_GRAPH_CACHE")
    cache_expiry_hours: int = Field(default=24, alias="CACHE_EXPIRY_HOURS")

    def model_post_init(self, __context) -> None:
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.osm_cache_dir.mkdir(parents=True, exist_ok=True)
        self.elevation_cache_dir.mkdir(parents=True, exist_ok=True)
        self.graph_cache_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
