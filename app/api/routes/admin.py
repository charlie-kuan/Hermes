"""Admin API routes for managing areas, points, and routes."""

import csv
import json
import os
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.utils.logger import logger

router = APIRouter()

AREAS_DIR = lambda: settings.data_dir / "areas"
INDEX_FILE = lambda: AREAS_DIR() / "_index.json"


# --- Models ---

class AreaCreate(BaseModel):
    area_id: str
    name: str
    description: str = ""


class AreaUpdate(BaseModel):
    name: str
    description: str = ""


class PointUpsert(BaseModel):
    id: str
    name: str
    type: str
    lat: float
    lon: float
    elevation: float
    description: str = ""
    facilities: List[str] = []
    capacity: Optional[int] = None


class RouteUpsert(BaseModel):
    route_id: str
    name: str
    description: str = ""
    days: int
    difficulty: str
    estimated_distance: Optional[float] = None
    estimated_time: str = ""
    point_sequence: List[str] = []
    highlight: str = ""


# --- Helpers ---

def _load_index() -> List[dict]:
    f = INDEX_FILE()
    if not f.exists():
        return []
    with open(f, "r", encoding="utf-8") as fp:
        return json.load(fp).get("areas", [])


def _save_index(areas: List[dict]):
    with open(INDEX_FILE(), "w", encoding="utf-8") as fp:
        json.dump({"areas": areas}, fp, ensure_ascii=False, indent=2)


def _points_file(area_id: str) -> Path:
    return AREAS_DIR() / area_id / "points.csv"


def _routes_file(area_id: str) -> Path:
    return AREAS_DIR() / area_id / "routes.csv"


POINTS_FIELDS = ["id", "name", "type", "lat", "lon", "elevation", "description", "facilities", "capacity"]
ROUTES_FIELDS = ["route_id", "name", "description", "days", "difficulty",
                 "estimated_distance", "estimated_time", "point_sequence", "highlight"]


def _read_points(area_id: str) -> List[dict]:
    f = _points_file(area_id)
    if not f.exists():
        return []
    with open(f, "r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def _write_points(area_id: str, points: List[dict]):
    f = _points_file(area_id)
    with open(f, "w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=POINTS_FIELDS)
        writer.writeheader()
        writer.writerows(points)


def _read_routes(area_id: str) -> List[dict]:
    f = _routes_file(area_id)
    if not f.exists():
        return []
    with open(f, "r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def _write_routes(area_id: str, routes: List[dict]):
    f = _routes_file(area_id)
    with open(f, "w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=ROUTES_FIELDS)
        writer.writeheader()
        writer.writerows(routes)


def _area_exists(area_id: str) -> bool:
    return any(a["area_id"] == area_id for a in _load_index())


# --- Area endpoints ---

@router.get("/admin/areas", tags=["Admin"])
async def admin_list_areas():
    areas = _load_index()
    result = []
    for a in areas:
        aid = a["area_id"]
        points = _read_points(aid)
        routes = _read_routes(aid)
        result.append({**a, "point_count": len(points), "route_count": len(routes)})
    return {"areas": result}


@router.post("/admin/areas", tags=["Admin"], status_code=201)
async def admin_create_area(body: AreaCreate):
    areas = _load_index()
    if any(a["area_id"] == body.area_id for a in areas):
        raise HTTPException(status_code=409, detail=f"Area {body.area_id} already exists")
    areas.append({"area_id": body.area_id, "name": body.name, "description": body.description})
    _save_index(areas)
    # Create directory and empty CSVs
    area_dir = AREAS_DIR() / body.area_id
    area_dir.mkdir(parents=True, exist_ok=True)
    _write_points(body.area_id, [])
    _write_routes(body.area_id, [])
    return {"area_id": body.area_id, "name": body.name}


@router.put("/admin/areas/{area_id}", tags=["Admin"])
async def admin_update_area(area_id: str, body: AreaUpdate):
    areas = _load_index()
    for a in areas:
        if a["area_id"] == area_id:
            a["name"] = body.name
            a["description"] = body.description
            _save_index(areas)
            return a
    raise HTTPException(status_code=404, detail=f"Area {area_id} not found")


@router.delete("/admin/areas/{area_id}", tags=["Admin"])
async def admin_delete_area(area_id: str):
    areas = _load_index()
    new_areas = [a for a in areas if a["area_id"] != area_id]
    if len(new_areas) == len(areas):
        raise HTTPException(status_code=404, detail=f"Area {area_id} not found")
    _save_index(new_areas)
    area_dir = AREAS_DIR() / area_id
    if area_dir.exists():
        shutil.rmtree(area_dir)
    return {"deleted": area_id}


# --- Point endpoints ---

@router.get("/admin/areas/{area_id}/points", tags=["Admin"])
async def admin_list_points(area_id: str):
    if not _area_exists(area_id):
        raise HTTPException(status_code=404, detail=f"Area {area_id} not found")
    return {"points": _read_points(area_id)}


@router.post("/admin/areas/{area_id}/points", tags=["Admin"], status_code=201)
async def admin_upsert_point(area_id: str, body: PointUpsert):
    if not _area_exists(area_id):
        raise HTTPException(status_code=404, detail=f"Area {area_id} not found")
    points = _read_points(area_id)
    row = {
        "id": body.id,
        "name": body.name,
        "type": body.type,
        "lat": body.lat,
        "lon": body.lon,
        "elevation": body.elevation,
        "description": body.description or "",
        "facilities": ";".join(body.facilities),
        "capacity": body.capacity if body.capacity is not None else "",
    }
    # Upsert by id
    existing = next((i for i, p in enumerate(points) if p["id"] == body.id), None)
    if existing is not None:
        points[existing] = row
    else:
        points.append(row)
    _write_points(area_id, points)
    return row


@router.delete("/admin/areas/{area_id}/points/{point_id}", tags=["Admin"])
async def admin_delete_point(area_id: str, point_id: str):
    if not _area_exists(area_id):
        raise HTTPException(status_code=404, detail=f"Area {area_id} not found")
    points = _read_points(area_id)
    new_points = [p for p in points if p["id"] != point_id]
    if len(new_points) == len(points):
        raise HTTPException(status_code=404, detail=f"Point {point_id} not found")
    _write_points(area_id, new_points)
    return {"deleted": point_id}


# --- Route endpoints ---

@router.get("/admin/areas/{area_id}/routes", tags=["Admin"])
async def admin_list_routes(area_id: str):
    if not _area_exists(area_id):
        raise HTTPException(status_code=404, detail=f"Area {area_id} not found")
    return {"routes": _read_routes(area_id)}


@router.post("/admin/areas/{area_id}/routes", tags=["Admin"], status_code=201)
async def admin_upsert_route(area_id: str, body: RouteUpsert):
    if not _area_exists(area_id):
        raise HTTPException(status_code=404, detail=f"Area {area_id} not found")
    routes = _read_routes(area_id)
    row = {
        "route_id": body.route_id,
        "name": body.name,
        "description": body.description or "",
        "days": body.days,
        "difficulty": body.difficulty,
        "estimated_distance": body.estimated_distance if body.estimated_distance is not None else "",
        "estimated_time": body.estimated_time or "",
        "point_sequence": ">".join(body.point_sequence),
        "highlight": body.highlight or "",
    }
    existing = next((i for i, r in enumerate(routes) if r["route_id"] == body.route_id), None)
    if existing is not None:
        routes[existing] = row
    else:
        routes.append(row)
    _write_routes(area_id, routes)
    return row


@router.delete("/admin/areas/{area_id}/routes/{route_id}", tags=["Admin"])
async def admin_delete_route(area_id: str, route_id: str):
    if not _area_exists(area_id):
        raise HTTPException(status_code=404, detail=f"Area {area_id} not found")
    routes = _read_routes(area_id)
    new_routes = [r for r in routes if r["route_id"] != route_id]
    if len(new_routes) == len(routes):
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    _write_routes(area_id, new_routes)
    return {"deleted": route_id}
