#!/usr/bin/env python
"""
Download OSM river data for Taiwan and save as GeoPackage.

Steps:
  1. Download taiwan-latest.osm.pbf from Geofabrik (if not already cached)
  2. Parse with pyosmium to extract waterway=river (lines) and waterway=riverbank (polygons)
  3. Save to data/river/osm_rivers.gpkg

Output layers:
  river_lines  — waterway=river (LineString)
  river_polys  — waterway=riverbank (Polygon)

Usage:
  python scripts/download_osm_rivers.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import osmium
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Polygon
from tqdm import tqdm
from loguru import logger

PBF_URL  = "https://download.geofabrik.de/asia/taiwan-latest.osm.pbf"
PBF_PATH = Path("data/river/taiwan-latest.osm.pbf")
OUT_PATH = Path("data/river/osm_rivers.gpkg")


# ── Step 1: download PBF ─────────────────────────────────────────────────────

def download_pbf():
    if PBF_PATH.exists():
        logger.info(f"PBF already exists ({PBF_PATH.stat().st_size / 1e6:.0f} MB), skipping download.")
        return
    PBF_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading {PBF_URL} ...")
    with requests.get(PBF_URL, stream=True, timeout=300) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        with open(PBF_PATH, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, desc="taiwan.osm.pbf"
        ) as bar:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                bar.update(len(chunk))
    logger.info("Download complete.")


# ── Step 2: parse PBF ────────────────────────────────────────────────────────

class RiverHandler(osmium.SimpleHandler):
    """Extract waterway=river (lines) and waterway=riverbank (polygons)."""

    def __init__(self):
        super().__init__()
        self.lines = []   # (osm_id, name, name_zh, geometry)
        self.polys = []

    def way(self, w):
        waterway = w.tags.get("waterway", "")
        if waterway not in ("river", "riverbank"):
            return
        try:
            coords = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if len(coords) < 2:
            return

        name    = w.tags.get("name",    "")
        name_zh = w.tags.get("name:zh", "")
        osm_id  = w.id

        if waterway == "river":
            if len(coords) >= 2:
                self.lines.append((osm_id, name, name_zh, LineString(coords)))
        else:  # riverbank
            if len(coords) >= 4:
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                self.polys.append((osm_id, name, name_zh, Polygon(coords)))


def parse_pbf() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    logger.info("Parsing PBF (this may take a minute)...")
    handler = RiverHandler()
    # locations=True so node coordinates are resolved inside ways
    handler.apply_file(str(PBF_PATH), locations=True)

    def to_gdf(rows):
        if not rows:
            return gpd.GeoDataFrame(
                columns=["osm_id", "name", "name_zh", "geometry"], crs="EPSG:4326"
            )
        df = pd.DataFrame(rows, columns=["osm_id", "name", "name_zh", "geometry"])
        return gpd.GeoDataFrame(df, crs="EPSG:4326")

    lines = to_gdf(handler.lines)
    polys = to_gdf(handler.polys)
    logger.info(f"  river lines   : {len(lines)}")
    logger.info(f"  river polygons: {len(polys)}")
    return lines, polys


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    download_pbf()
    lines, polys = parse_pbf()

    lines.to_file(OUT_PATH, layer="river_lines", driver="GPKG")
    polys.to_file(OUT_PATH, layer="river_polys", driver="GPKG")

    logger.success(f"Saved → {OUT_PATH}")


if __name__ == "__main__":
    main()
