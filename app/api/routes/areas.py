"""Areas endpoint handlers."""

from fastapi import APIRouter, HTTPException

from app.models.responses import AreaListResponse, AreaResponse
from app.utils.area_loader import load_all_areas, load_area_full

router = APIRouter()


def load_areas() -> list[dict]:
    """Load available areas from data/areas structure."""
    return load_all_areas()


@router.get("/areas", response_model=AreaListResponse, tags=["Areas"])
async def list_areas():
    """
    Get list of available hiking areas.

    Returns a list of all configured hiking areas with their metadata.
    """
    areas = [AreaResponse(**area) for area in load_areas()]

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
    area = load_area_full(area_id)
    if area:
        return AreaResponse(**area)

    raise HTTPException(status_code=404, detail=f"Area {area_id} not found")
