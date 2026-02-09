"""Areas endpoint handlers."""

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.responses import AreaListResponse, AreaResponse

router = APIRouter()


def load_areas() -> List[dict]:
    """Load available areas from areas.json."""
    areas_file = settings.data_dir / "areas.json"

    if not areas_file.exists():
        return []

    try:
        with open(areas_file, 'r') as f:
            data = json.load(f)
            return data.get('areas', [])
    except Exception as e:
        return []


@router.get("/areas", response_model=AreaListResponse, tags=["Areas"])
async def list_areas():
    """
    Get list of available hiking areas.

    Returns a list of all configured hiking areas with their metadata.
    """
    areas_data = load_areas()

    areas = [AreaResponse(**area) for area in areas_data]

    return AreaListResponse(
        areas=areas,
        total=len(areas)
    )


@router.get("/areas/{area_id}", response_model=AreaResponse, tags=["Areas"])
async def get_area(area_id: str):
    """
    Get details for a specific hiking area.

    Args:
        area_id: Area identifier

    Returns:
        Area details including bounding box and statistics
    """
    areas_data = load_areas()

    for area in areas_data:
        if area['area_id'] == area_id:
            return AreaResponse(**area)

    raise HTTPException(status_code=404, detail=f"Area {area_id} not found")
