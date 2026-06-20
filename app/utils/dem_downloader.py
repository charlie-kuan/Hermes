"""Auto-download DEM file on startup if not present."""

import asyncio
import io
import time
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
ZIP_TMP = "dem_tmp.zip"
MAX_RETRIES = 5


def _find_tif_in_zip(zf: zipfile.ZipFile) -> str | None:
    for name in zf.namelist():
        if name.lower().endswith((".tif", ".tiff")):
            return name
    return None


def _download_with_resume(url: str, tmp_path: Path) -> None:
    """Download with resume support and retry on failure."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ProjectHermes/1.0)"}

    for attempt in range(1, MAX_RETRIES + 1):
        downloaded = tmp_path.stat().st_size if tmp_path.exists() else 0
        if downloaded > 0:
            logger.info(f"Resuming download from {downloaded // 1024 // 1024}MB (attempt {attempt}/{MAX_RETRIES})")
            headers["Range"] = f"bytes={downloaded}-"
        else:
            logger.info(f"Starting download (attempt {attempt}/{MAX_RETRIES})...")
            headers.pop("Range", None)

        try:
            with httpx.Client(timeout=3600, follow_redirects=True, headers=headers) as client:
                with client.stream("GET", url) as resp:
                    if resp.status_code == 416:
                        logger.info("File already fully downloaded.")
                        return
                    resp.raise_for_status()

                    # If server ignores Range and returns 200, start over
                    if downloaded > 0 and resp.status_code == 200:
                        logger.warning("Server does not support resume, restarting download...")
                        downloaded = 0
                        tmp_path.unlink(missing_ok=True)

                    total = int(resp.headers.get("content-length", 0))
                    if total:
                        full_size = downloaded + total
                        logger.info(f"Total size: {full_size // 1024 // 1024}MB")

                    mode = "ab" if downloaded > 0 else "wb"
                    with open(tmp_path, mode) as f:
                        for chunk in resp.iter_bytes(chunk_size=2 * 1024 * 1024):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total and downloaded % (50 * 1024 * 1024) < 2 * 1024 * 1024:
                                pct = downloaded / (downloaded + total - len(chunk)) * 100
                                logger.info(f"Progress: {downloaded // 1024 // 1024}MB ({pct:.0f}%)")
            logger.info("Download complete.")
            return

        except (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectError) as e:
            logger.warning(f"Download interrupted: {e}")
            if attempt < MAX_RETRIES:
                wait = 10 * attempt
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Download failed after {MAX_RETRIES} attempts") from e


def _download_and_extract(dem_dir: Path) -> None:
    tmp_path = dem_dir / ZIP_TMP
    dem_path = dem_dir / DEM_FILENAME

    logger.info("Downloading DEM from tgos.tw (~700MB), this may take a while...")
    _download_with_resume(DEM_URL, tmp_path)

    logger.info("Extracting ZIP...")
    with zipfile.ZipFile(tmp_path) as zf:
        tif_name = _find_tif_in_zip(zf)
        if not tif_name:
            raise RuntimeError("No .tif file found inside the downloaded ZIP")
        logger.info(f"Extracting {tif_name} -> {dem_path}")
        dem_path.write_bytes(zf.read(tif_name))

    tmp_path.unlink(missing_ok=True)
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
