"""Auto-download DEM file on startup if not present."""

import asyncio
import io
import zipfile
from pathlib import Path

import httpx
from loguru import logger

DEM_URL = (
    "https://www.tgos.tw:443/MDE/VirtualDir_TC/Product/"
    "528530be-0710-431e-954e-2f2f5e98b0c5/"
    "不分幅_全台20MDEM(2025).zip"
)
DEM_FILENAME = "DEM_tawiwan_V2025.tif"


def _find_tif_in_zip(zf: zipfile.ZipFile) -> str | None:
    for name in zf.namelist():
        if name.lower().endswith((".tif", ".tiff")):
            return name
    return None


def _download_and_extract(dem_dir: Path) -> None:
    dem_path = dem_dir / DEM_FILENAME
    logger.info(f"Downloading DEM from tgos.tw (~700MB), this may take a while...")

    headers = {"User-Agent": "Mozilla/5.0 (compatible; ProjectHermes/1.0)"}
    with httpx.Client(timeout=3600, follow_redirects=True, headers=headers) as client:
        with client.stream("GET", DEM_URL) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            chunks = []
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                chunks.append(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    if downloaded % (50 * 1024 * 1024) < 1024 * 1024:
                        logger.info(f"DEM download progress: {pct:.1f}% ({downloaded // 1024 // 1024}MB / {total // 1024 // 1024}MB)")
            data = b"".join(chunks)

    logger.info("Download complete, extracting ZIP...")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        tif_name = _find_tif_in_zip(zf)
        if not tif_name:
            raise RuntimeError("No .tif file found inside the downloaded ZIP")
        logger.info(f"Extracting {tif_name} -> {dem_path}")
        dem_path.write_bytes(zf.read(tif_name))

    logger.info(f"DEM file ready: {dem_path} ({dem_path.stat().st_size // 1024 // 1024}MB)")


async def ensure_dem_exists(dem_dir: Path) -> None:
    """Check for DEM file and download if missing. Runs in a thread to avoid blocking."""
    dem_path = dem_dir / DEM_FILENAME
    if dem_path.exists() and dem_path.stat().st_size > 100 * 1024 * 1024:
        logger.info(f"DEM file already present: {dem_path}")
        return

    if dem_path.exists():
        logger.warning(f"DEM file seems incomplete ({dem_path.stat().st_size} bytes), re-downloading...")
        dem_path.unlink()

    logger.info("DEM file not found, starting background download...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _download_and_extract, dem_dir)
